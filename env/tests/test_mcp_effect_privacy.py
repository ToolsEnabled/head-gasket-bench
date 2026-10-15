"""StringIO MCP transport control, not a real subject isolation qualification."""
import contextlib
import ctypes as c
import io
import os
import json
import tempfile
import unittest
from pathlib import Path
from hgj.codec import digest
from hgj.game import Game,replay
from hgj.mcp import serve
from tests.test_game_condition_effects import GameConditionEffectsTests

class McpEffectPrivacyTests(unittest.TestCase):
    def assert_private_windows_file(self, path):
        # Real native readback, not chmod/stat mode emulation. The run-folder
        # lease stays held while these exact, non-delete-shared files are open.
        from headgasket import windows_folder as win
        handle = win.open_file(str(path), 0x20080, 3, None, 3, 0x00200000, None)
        if handle == win.INVALID:
            raise c.WinError(c.get_last_error())
        try:
            info = win.FileInfo()
            win.check(win.file_info(handle, c.byref(info)))
            self.assertEqual(info.attributes & (0x10 | 0x400), 0, 'private output must be a plain file')
            self.assertEqual(info.links, 1, 'private output must not have another hard link')
            self.assertNotEqual((info.index_hi, info.index_lo), (0, 0))
            owner, dacl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
            error = win.get_security(handle, 1, 5, c.byref(owner), None,
                                     c.byref(dacl), None, c.byref(descriptor))
            if error:
                raise c.WinError(error)
            try:
                self.assertTrue(dacl.value, 'private output must have a non-null DACL')
                sid = win.user()
                trusted = {sid, 'S-1-5-18', 'S-1-5-32-544'}
                # A high token can default new file ownership to BA. The product
                # still requires current-SID ownership of the private run folder.
                self.assertIn(win._sid_text(owner), {sid, 'S-1-5-32-544'})
                details = win.AclInfo()
                win.check(win.acl_info(dacl, c.byref(details), c.sizeof(details), 2))
                rows = []
                for index in range(details.count):
                    ace = c.c_void_p()
                    win.check(win.get_ace(dacl, index, c.byref(ace)))
                    kind = c.c_ubyte.from_address(ace.value).value
                    flags = c.c_ubyte.from_address(ace.value + 1).value
                    self.assertEqual(kind, 0, 'unknown or non-allow private file ACE')
                    self.assertIn(flags, (0, 0x10), 'private file ACE must be effective and ordinary')
                    rows.append({'sid': win._sid_text(c.c_void_p(ace.value + 8)),
                                 'mask': win.w.DWORD.from_address(ace.value + 4).value,
                                 'flags': flags})
                print('HGB_NATIVE_PRIVATE_FILE_ACL ' + json.dumps({
                    'file': path.name, 'owner': win._sid_text(owner), 'aces': rows,
                    'volume': info.volume, 'fileId': [info.index_hi, info.index_lo]}))
                self.assertEqual({row['sid'] for row in rows}, trusted,
                                 'private file grants access outside private allowlist')
                self.assertEqual(len(rows), 3, 'private file ACL census differs')
                self.assertTrue(all(row['mask'] == 0x1f01ff for row in rows))
            finally:
                win.free(descriptor)
        finally:
            win.check(win.close(handle))

    def test_private_effect_packet_is_journalled_but_unreachable_from_tool_surface(self):
        fixtures=GameConditionEffectsTests();self.addCleanup(fixtures.doCleanups)
        config,backend=fixtures.fixture();game=Game(config,joint=backend)
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as custody:
            root=Path(directory);planted=root/'planted.txt';planted.write_text('PLANTED_TOOL_SURFACE_ONLY')
            requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'resources/read','params':{'uri':str(planted)}},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_file','arguments':{'path':str(planted)}}},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'clean','arguments':config['action_domains']['rules'][0]['arguments']}},
                {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'inspect','arguments':{'target':str(planted)}}}]
            if os.name == 'nt':
                from headgasket import windows_folder as win
                self.assertTrue(win.create_run_directory(root/'host-run'))
                custody.callback(win.lock_folder(root/'host-run').close)
            incoming=io.StringIO(''.join(json.dumps(r)+'\n' for r in requests));outgoing=io.StringIO()
            result=serve(game,incoming,outgoing,root/'host-run')
            transcript=outgoing.getvalue();responses={r['id']:r for r in map(json.loads,transcript.splitlines())}
            self.assertEqual(responses[2]['error']['code'],-32601)
            self.assertTrue(responses[3]['result']['isError']);self.assertTrue(responses[5]['result']['isError'])
            self.assertFalse(responses[4]['result']['isError'])
            for hidden in ('PLANTED_TOOL_SURFACE_ONLY','authorized_condition_effects','condition_sources',
                           backend.descriptor['sha256'],config['identity']['action_domains_sha256']):
                self.assertNotIn(hidden,transcript)
            run=json.loads((root/'host-run/run.json').read_text())
            journal=[json.loads(line) for line in (root/'host-run/actions.jsonl').read_text().splitlines()]
            self.assertEqual(journal,run['actions']);self.assertEqual(result['actions'],3)
            effect=journal[1]['authorized_condition_effects']
            self.assertIs(journal[1]['condition_effects_committed'],True)
            self.assertEqual(effect['operation']['attempt_sequence'],2)
            self.assertEqual(effect['operation_sha256'],digest(effect['operation']))
            self.assertEqual(replay(run,joint=backend),run)
            for name in ('run.json','actions.jsonl'):
                if os.name == 'nt':
                    self.assert_private_windows_file(root/'host-run'/name)
                else:
                    self.assertEqual((root/'host-run'/name).stat().st_mode&0o777,0o600)
            if os.name == 'nt':
                # Author one NEW unsafe descriptor; do not repair any existing
                # product output. Its outside read grant must be detected.
                descriptor = c.c_void_p()
                sid = win.user()
                sddl = f'O:{sid}G:{sid}D:P(A;;FA;;;{sid})(A;;FA;;;SY)(A;;FA;;;BA)(A;;FR;;;WD)'
                win.check(win.descriptor_parse(sddl, 1, c.byref(descriptor), None))
                try:
                    security = win.Security(c.sizeof(win.Security), descriptor, False)
                    unsafe = root/'unsafe-read.txt'
                    handle = win.open_file(str(unsafe), 0x20080, 3, c.byref(security), 1, 0x80, None)
                    if handle == win.INVALID:
                        raise c.WinError(c.get_last_error())
                    win.check(win.close(handle))
                finally:
                    win.free(descriptor)
                with self.assertRaisesRegex(AssertionError, 'outside private allowlist'):
                    self.assert_private_windows_file(unsafe)
