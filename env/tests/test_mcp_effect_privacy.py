"""StringIO MCP transport control, not a real subject isolation qualification."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from hgj.codec import digest
from hgj.game import Game,replay
from hgj.mcp import serve
from tests.test_game_condition_effects import GameConditionEffectsTests

class McpEffectPrivacyTests(unittest.TestCase):
    def test_private_effect_packet_is_journalled_but_unreachable_from_tool_surface(self):
        fixtures=GameConditionEffectsTests();self.addCleanup(fixtures.doCleanups)
        config,backend=fixtures.fixture();game=Game(config,joint=backend)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);planted=root/'planted.txt';planted.write_text('PLANTED_TOOL_SURFACE_ONLY')
            requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'resources/read','params':{'uri':str(planted)}},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_file','arguments':{'path':str(planted)}}},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'clean','arguments':config['action_domains']['rules'][0]['arguments']}},
                {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'inspect','arguments':{'target':str(planted)}}}]
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
                self.assertEqual((root/'host-run'/name).stat().st_mode&0o777,0o600)
