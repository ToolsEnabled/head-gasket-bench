"""The public launcher: pins, a real stdio session, replay, verify and validate.

Runs the launcher as a child process the way an MCP client would. No model.
"""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'bin' / 'headgasket-mcp'
PINS = json.loads((ROOT / 'configs' / 'PINS.json').read_bytes())


def run(*args, stdin=b'', check=True):
    completed = subprocess.run([sys.executable, '-B', str(LAUNCHER), *args], input=stdin, cwd=tempfile.gettempdir(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if check and completed.returncode != 0:
        raise AssertionError(f'{args}: exit {completed.returncode}\n{completed.stderr.decode()}')
    return completed


def session(calls):
    rows = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}]
    rows += [{'jsonrpc': '2.0', 'id': index + 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}}
             for index, (name, arguments) in enumerate(calls)]
    return b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode() for row in rows)


class PinTests(unittest.TestCase):
    def test_pins_check_passes_and_lists_nineteen_files(self):
        result = json.loads(run('pins', '--check').stdout)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['files']), 19)
        self.assertTrue(all(item['ok'] for item in result['files'].values()))
        self.assertEqual(set(result['configurations']), {'V1', 'V2', 'V3', 'V4', 'V5'})
        self.assertTrue(all(item['ok'] for item in result['configurations'].values()))
        manifest = (ROOT / 'data' / 'environment-source.json').read_bytes()
        self.assertEqual(hashlib.sha256(manifest).hexdigest(), PINS['source_manifest_sha256'])

    def test_pins_check_covers_both_runtime_epochs(self):
        result = json.loads(run('pins', '--check').stdout)
        self.assertEqual(set(result['epochs']), {'hardened-v6-aecadda', 'amended-v5-24a5713'})
        for epoch in result['epochs'].values():
            self.assertTrue(epoch['ok'])
            self.assertEqual((epoch['files_ok'], epoch['files']), (19, 19))

    def test_amended_epoch_runtime_is_selected_by_its_manifest_pin(self):
        sys.path.insert(0, str(ROOT))
        from headgasket import cli
        pin = PINS['epochs']['amended-v5-24a5713']['source_manifest_sha256']
        runtime = cli.runtime_for(cli.load_pins(), pin)
        self.assertEqual(runtime.identity['source_manifest_sha256'], pin)
        self.assertEqual(runtime.root, (ROOT / 'epochs' / 'amended-v5').resolve())
        current = cli.runtime_for(cli.load_pins())
        self.assertEqual(current.identity['source_manifest_sha256'], PINS['source_manifest_sha256'])
        with self.assertRaises(cli.Failure):
            cli.runtime_for(cli.load_pins(), '0' * 64)

    def test_prepare_regenerates_the_pinned_v1_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'V1.json'
            result = json.loads(run('prepare', '--variant', 'V1', '--out', str(target)).stdout)
            self.assertEqual(result['sha256'], PINS['configurations']['V1']['sha256'])
            self.assertEqual(target.read_bytes(), (ROOT / 'configs' / 'V1.configuration.json').read_bytes())

    def test_tools_lists_the_eighteen_tools(self):
        names = [json.loads(line)['name'] for line in run('tools', '--json').stdout.decode().splitlines()]
        self.assertEqual(len(names), 18)
        self.assertEqual(names[0], 'look')
        self.assertEqual(names[-1], 'finish')


class StdioSessionTests(unittest.TestCase):
    def test_serve_replay_verify_and_validate_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            completed = run('serve', '--variant', 'V1', '--out', str(out),
                            stdin=session([('look', {}), ('parts_bin', {}), ('torque', {'part_id': 'nothing', 'mode': 'tighten', 'value_N_m': 1})]))
            replies = [json.loads(line) for line in completed.stdout.decode().splitlines()]
            self.assertEqual([row['id'] for row in replies], [0, 1, 2, 3, 4])
            self.assertEqual(replies[0]['result']['serverInfo']['name'], 'headgasket')
            self.assertEqual(len(replies[1]['result']['tools']), 18)
            look = json.loads(replies[2]['result']['content'][0]['text'])
            self.assertTrue(look['ok']); self.assertFalse(replies[2]['result']['isError'])
            self.assertEqual(look['turns_remaining'], 1023)
            refused = json.loads(replies[4]['result']['content'][0]['text'])
            self.assertFalse(refused['ok']); self.assertTrue(replies[4]['result']['isError'])
            for name in ('run.json', 'actions.jsonl', 'report.json', 'launch.json'):
                self.assertTrue((out / name).is_file(), name)
            self.assertFalse((out / 'finish-record.json').exists())
            record = json.loads((out / 'run.json').read_bytes())
            self.assertEqual(record['schema'], 'hgj/run/v2')
            self.assertEqual(record['config_sha256'], PINS['configurations']['V1']['sha256'])
            self.assertEqual(record['environment_source']['source_manifest_sha256'], PINS['source_manifest_sha256'])
            self.assertEqual([row['name'] for row in record['actions']], ['look', 'parts_bin', 'torque'])
            self.assertEqual(record['actions'][0]['previous_action_sha256'], record['config_sha256'])
            self.assertFalse(record['finished'])
            launch = json.loads((out / 'launch.json').read_bytes())
            self.assertEqual((launch['variant'], launch['actions'], launch['finished']), ('V1', 3, False))

            replayed = json.loads(run('replay', '--record', str(out / 'run.json'), '--out', str(Path(folder) / 'replay.json')).stdout)
            self.assertTrue(replayed['ok'] and replayed['exact'])
            self.assertEqual((Path(folder) / 'replay.json').read_bytes(), (out / 'run.json').read_bytes())

            verified = json.loads(run('verify', '--run', str(out)).stdout)
            self.assertTrue(verified['ok'])
            self.assertTrue(verified['checks']['exact_replay'] and verified['checks']['actions_jsonl'] and verified['checks']['report_json'])
            self.assertEqual(verified['checks']['terminal_reason'], 'input_ended_without_finish')

            # The repository validator refuses an unfinished run.
            refused = run('validate', str(out), check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('the run did not finish', refused.stderr.decode())

            # A changed record no longer replays.
            damaged = dict(record); damaged['actions'] = record['actions'][:2]
            (Path(folder) / 'damaged.json').write_bytes((json.dumps(damaged, sort_keys=True, separators=(',', ':')) + '\n').encode())
            broken = run('replay', '--record', str(Path(folder) / 'damaged.json'), check=False)
            self.assertEqual(broken.returncode, 1)
            self.assertIn('replay', broken.stderr.decode())

    def test_serve_refuses_a_used_folder_and_a_wrong_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            run('serve', '--variant', 'V2', '--out', str(out), stdin=session([('look', {})]))
            again = run('serve', '--variant', 'V2', '--out', str(out), stdin=session([]), check=False)
            self.assertEqual(again.returncode, 1)
            self.assertIn('already holds a run', again.stderr.decode())
            wrong = run('serve', '--config', str(ROOT / 'configs' / 'V2.configuration.json'), '--config-pin', '0' * 64,
                        '--out', str(Path(folder) / 'other'), stdin=session([]), check=False)
            self.assertEqual(wrong.returncode, 1)
            self.assertIn('differs from the pin', wrong.stderr.decode())
            self.assertFalse((Path(folder) / 'other').exists())


class ServeFolderTests(unittest.TestCase):
    """What serve does with its --out folder and its input (0.1.2)."""

    def test_a_start_without_tool_calls_leaves_nothing_behind(self):
        # A client health check (claude mcp list) starts the server, lists the tools and
        # stops it. That must not use up the folder of the real session.
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            probe = run('serve', '--variant', 'V1', '--out', str(out), stdin=session([]))
            self.assertIn('no tool calls', probe.stderr.decode())
            self.assertFalse(out.exists())
            real = run('serve', '--variant', 'V1', '--out', str(out), stdin=session([('parts_bin', {})]))
            self.assertIn('1 actions', real.stderr.decode())
            self.assertEqual(len(json.loads((out / 'run.json').read_bytes())['actions']), 1)

    def test_an_empty_folder_given_by_the_user_is_kept_after_a_probe(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            out.mkdir()
            run('serve', '--variant', 'V1', '--out', str(out), stdin=session([]))
            self.assertTrue(out.is_dir())
            self.assertEqual(list(out.iterdir()), [])

    def test_what_a_killed_start_left_behind_is_cleared(self):
        # A client that kills the server right after listing its tools leaves an empty
        # journal and a partly written temporary record.
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            out.mkdir()
            (out / 'actions.jsonl').write_bytes(b'')
            (out / 'run.json.tmp').write_bytes(b'{"partial')
            served = run('serve', '--variant', 'V1', '--out', str(out), stdin=session([('look', {})]))
            self.assertIn('removed what an earlier start without any tool call left behind', served.stderr.decode())
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['actions.jsonl', 'launch.json', 'report.json', 'run.json'])
            self.assertEqual(len(json.loads((out / 'run.json').read_bytes())['actions']), 1)

    def test_a_folder_with_other_files_or_a_journal_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            other = Path(folder) / 'other'
            other.mkdir()
            (other / 'notes.txt').write_text('mine')
            refused = run('serve', '--variant', 'V1', '--out', str(other), stdin=session([]), check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('holds other files', refused.stderr.decode())
            self.assertEqual((other / 'notes.txt').read_text(), 'mine')
            started = Path(folder) / 'started'
            started.mkdir()
            (started / 'actions.jsonl').write_bytes(b'{"seq":1}\n')
            refused = run('serve', '--variant', 'V1', '--out', str(started), stdin=session([]), check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('already holds a run', refused.stderr.decode())
            self.assertEqual((started / 'actions.jsonl').read_bytes(), b'{"seq":1}\n')

    def test_a_folder_in_use_by_another_server_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            first = subprocess.Popen([sys.executable, '-B', str(LAUNCHER), 'serve', '--variant', 'V1', '--out', str(out)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                first.stdin.write(session([]).splitlines(keepends=True)[0])
                first.stdin.flush()
                self.assertIn(b'"id":0', first.stdout.readline())
                second = run('serve', '--variant', 'V1', '--out', str(out), stdin=session([]), check=False)
                self.assertEqual(second.returncode, 1)
                self.assertIn('another headgasket server is using this folder', second.stderr.decode())
                self.assertTrue((out / 'actions.jsonl').is_file())
            finally:
                first.stdin.close()
                first.wait(timeout=300)
                first.stdout.close(); first.stderr.close()
            self.assertEqual(first.returncode, 0)

    def test_links_are_refused_and_nothing_is_written_through_them(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            victim = base / 'victim.txt'
            victim.write_text('untouched')
            (base / 'real').mkdir()
            (base / 'link').symlink_to('real')
            refused = run('serve', '--variant', 'V1', '--out', str(base / 'link'), stdin=session([('look', {})]), check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('symbolic link', refused.stderr.decode())
            (base / 'planted').mkdir()
            (base / 'planted' / 'run.json.tmp').symlink_to(victim)
            (base / 'planted' / 'launch.json').symlink_to(victim)
            refused = run('serve', '--variant', 'V1', '--out', str(base / 'planted'), stdin=session([('look', {})]),
                          check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('a link or something other than a regular file', refused.stderr.decode())
            self.assertEqual(victim.read_text(), 'untouched')
            self.assertEqual(list((base / 'real').iterdir()), [])

    def test_serve_needs_cpython_3_12(self):
        sys.path.insert(0, str(ROOT))
        from headgasket import cli
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            for name, version in (('cpython', (3, 13, 1)), ('cpython', (3, 11, 9)), ('pypy', (3, 12, 3))):
                stderr = io.StringIO()
                with mock.patch.object(cli, 'interpreter', return_value=(name, version)), contextlib.redirect_stderr(stderr):
                    code = cli.main(['serve', '--variant', 'V1', '--out', str(out)])
                self.assertEqual(code, 1)
                self.assertIn('serve needs CPython 3.12', stderr.getvalue())
                self.assertFalse(out.exists())

    def test_invalid_utf8_gets_an_error_and_the_session_goes_on(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            bad = b'{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"search_service_info","arguments":{"query":"caf\xe9"}}}\n'
            stdin = session([('parts_bin', {})]) + bad + b'{"jsonrpc":"2.0","id":6,"method":"ping"}\n'
            served = run('serve', '--variant', 'V1', '--out', str(out), stdin=stdin)
            replies = [json.loads(line) for line in served.stdout.decode().splitlines()]
            self.assertEqual(replies[-2]['error']['code'], -32602)
            self.assertEqual(replies[-1], {'id': 6, 'jsonrpc': '2.0', 'result': {}})
            report = json.loads((out / 'report.json').read_bytes())
            self.assertEqual(report['terminal_reason'], 'input_ended_without_finish')
            self.assertEqual(report['tool_calls']['attempted'], 1)

    def test_version_and_launch_record(self):
        self.assertEqual(run('--version').stdout.decode().strip(), 'headgasket 0.1.2')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            run('serve', '--variant', 'V1', '--out', str(out), stdin=session([('parts_bin', {})]))
            self.assertEqual(json.loads((out / 'launch.json').read_bytes())['version'], '0.1.2')
            self.assertEqual((out / 'launch.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(out.stat().st_mode & 0o077, 0)


if __name__ == '__main__':
    unittest.main()
