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

    def test_a_folder_other_users_can_write_to_is_refused(self):
        # verification of redteam F10: another local user could create --out in advance as
        # an empty folder anyone can write to and plant run.json.tmp -> victim after the
        # start check; the pinned server then overwrote the victim with the record.
        with tempfile.TemporaryDirectory() as folder:
            shared = Path(folder) / 'shared'
            shared.mkdir()
            os.chmod(shared, 0o777)
            refused = run('serve', '--variant', 'V1', '--out', str(shared), stdin=session([('parts_bin', {})]), check=False)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('other users can write to --out', refused.stderr.decode())
            self.assertEqual(list(shared.iterdir()), [])
            os.chmod(shared, 0o1777)  # sticky does not help: others can still create links in it
            refused = run('serve', '--variant', 'V1', '--out', str(shared), stdin=session([]), check=False)
            self.assertEqual(refused.returncode, 1)
            # A folder only its owner and group can write to (umask 002) is accepted.
            group = Path(folder) / 'group'
            group.mkdir()
            os.chmod(group, 0o775)
            run('serve', '--variant', 'V1', '--out', str(group), stdin=session([('parts_bin', {})]))
            self.assertEqual(len(json.loads((group / 'run.json').read_bytes())['actions']), 1)

    def test_a_folder_of_another_user_is_refused(self):
        sys.path.insert(0, str(ROOT))
        from headgasket import cli
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'theirs'
            out.mkdir()
            with mock.patch.object(cli.os, 'geteuid', return_value=os.geteuid() + 1):
                with self.assertRaises(cli.Failure) as caught:
                    cli.prepare_out(str(out))
            self.assertIn('belongs to another user', str(caught.exception))
            handle = cli.prepare_out(str(out))[2]
            os.close(handle)

    def test_version_and_launch_record(self):
        self.assertEqual(run('--version').stdout.decode().strip(), 'headgasket 0.1.3')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            run('serve', '--variant', 'V1', '--out', str(out), stdin=session([('parts_bin', {})]))
            self.assertEqual(json.loads((out / 'launch.json').read_bytes())['version'], '0.1.3')
            self.assertEqual((out / 'launch.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(out.stat().st_mode & 0o077, 0)


class BudgetTests(unittest.TestCase):
    """Calls after the budget is spent are answered by the launcher and not recorded (0.1.2).

    The pinned configurations allow 1,024 attempts; these tests use a copy of V1 with a
    budget of 3, served with --config and --config-pin."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config = json.loads((ROOT / 'configs' / 'V1.configuration.json').read_bytes())
        config['factors']['turn_budget'] = 3
        config['factors']['tool_call_limit'] = 3
        raw = (json.dumps(config, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
        self.config = Path(self.tmp.name) / 'small.json'
        self.config.write_bytes(raw)
        self.pin = hashlib.sha256(raw).hexdigest()
        self.out = Path(self.tmp.name) / 'run'

    def tearDown(self):
        self.tmp.cleanup()

    def serve(self, stdin):
        return run('serve', '--config', str(self.config), '--config-pin', self.pin, '--out', str(self.out), stdin=stdin)

    def test_calls_after_the_budget_are_refused_and_not_recorded(self):
        # verification of M2 / redteam F8: one call after turns_remaining reached 0 (a
        # finish, say) made a full-budget record of 1,025 attempts, which the pinned scorer
        # cannot score, so the run could not be submitted.
        served = self.serve(session([('parts_bin', {})] * 3 + [('finish', {}), ('look', {}), ('nonsense', 7)]))
        replies = [json.loads(line) for line in served.stdout.decode().splitlines()]
        self.assertEqual([row['id'] for row in replies], [0, 1, 2, 3, 4, 5, 6, 7])
        third = json.loads(replies[4]['result']['content'][0]['text'])
        self.assertEqual(third['turns_remaining'], 0)
        for reply in replies[5:]:
            self.assertTrue(reply['result']['isError'])
            self.assertEqual(json.loads(reply['result']['content'][0]['text']),
                             {'ok': False, 'refusal': 'Environment turn budget reached', 'turns_remaining': 0})
        self.assertIn('3 later tool calls were refused and not recorded', served.stderr.decode())
        record = json.loads((self.out / 'run.json').read_bytes())
        self.assertEqual(len(record['actions']), 3)
        self.assertEqual(record['budget']['attempted_calls'], 3)
        self.assertTrue(record['budget']['exhausted'])
        self.assertEqual(json.loads((self.out / 'report.json').read_bytes())['terminal_reason'], 'budget_exhausted')
        self.assertEqual(len((self.out / 'actions.jsonl').read_bytes().splitlines()), 3)
        replayed = json.loads(run('replay', '--record', str(self.out / 'run.json'), '--config', str(self.config),
                                  '--config-pin', self.pin).stdout)
        self.assertTrue(replayed['ok'] and replayed['exact'])

    def test_the_refusal_is_the_one_the_game_gives(self):
        sys.path.insert(0, str(ROOT))
        import importlib
        from headgasket import cli
        pins = cli.load_pins()
        runtime = cli.runtime_for(pins)
        config, _ = cli.load_config(self.config, self.pin)
        with runtime.active():
            game = importlib.import_module('hgj.game').Game(config, source_runtime=runtime)
            for _ in range(3):
                game.call('parts_bin', {})
            guard = cli.CallGuard(io.StringIO(), game, io.StringIO(), 65536)
            self.assertTrue(guard.spent())
            for name, arguments in (('finish', {}), ('parts_bin', {}), ('look', {})):
                self.assertEqual(game.call(name, arguments), cli.CallGuard.REFUSAL)

    def test_lines_the_server_refuses_anyway_still_reach_it(self):
        lines = session([('parts_bin', {})] * 3)
        lines += b'{"jsonrpc":"2.0","id":20,"method":"tools/call","params":{"name":"look","arguments":{"pad":"' + b'x' * 70000 + b'"}}}\n'
        lines += b'not json\n'
        lines += b'{"jsonrpc":"2.0","id":21,"method":"tools/call","params":"look"}\n'
        lines += b'{"jsonrpc":"2.0","id":22,"method":"ping"}\n'
        lines += b'{"jsonrpc":"2.0","id":23,"method":"tools/call","params":{"name":"look","arguments":{}}}'  # no newline at the end
        served = self.serve(lines)
        replies = [json.loads(line) for line in served.stdout.decode().splitlines()]
        tail = replies[-5:]
        self.assertEqual([row.get('error', {}).get('code') for row in tail[:3]], [-32602, -32602, -32602])
        self.assertEqual(tail[3], {'id': 22, 'jsonrpc': '2.0', 'result': {}})
        self.assertEqual(tail[4]['id'], 23)
        self.assertTrue(tail[4]['result']['isError'])
        self.assertEqual(len(json.loads((self.out / 'run.json').read_bytes())['actions']), 3)

    def test_before_the_budget_is_spent_every_call_reaches_the_game(self):
        served = self.serve(session([('parts_bin', {}), ('nonsense', {})]))
        replies = [json.loads(line) for line in served.stdout.decode().splitlines()]
        refused = json.loads(replies[-1]['result']['content'][0]['text'])
        self.assertFalse(refused['ok'])
        self.assertNotEqual(refused['refusal'], 'Environment turn budget reached')
        self.assertEqual(len(json.loads((self.out / 'run.json').read_bytes())['actions']), 2)
        self.assertNotIn('later tool calls', served.stderr.decode())



def replies_of(served):
    return [json.loads(line) for line in served.stdout.decode().splitlines()]


def value_of(reply):
    return json.loads(reply['result']['content'][0]['text'])


def route_refusal(part, routes, turns_remaining):
    return {'ok': False, 'turns_remaining': turns_remaining,
            'refusal': f'REMOVAL_POLICY_REFUSED: unknown requested route for part_id {part!r}; its routes are '
                       + ', '.join(map(repr, routes)) + ' (name one as route_id, or leave route_id out)'}


COVER_ROUTES = ['lift-after-fasteners-and-external-ties']


class RouteTests(unittest.TestCase):
    """A remove naming a route the part does not have is answered by the launcher and
    not recorded (0.1.3).

    The pinned game refuses it, but its scoring step then fails on the unknown route, and
    the server answers that call and every later one with a JSON-RPC error. The calls
    and routes below are environment identifiers; the first injected one is the call that
    stopped a model run on 2026-10-14."""

    def test_the_call_is_refused_and_the_run_goes_on(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            served = run('serve', '--variant', 'V1', '--out', str(out), stdin=session([
                ('remove', {'part_id': 'cover', 'route_id': 'no-such-route'}),
                ('look', {}),
                ('remove', {'part_id': 'cover', 'route_id': 7}),
                ('remove', {'part_id': 'cover', 'route_id': ''}),
                ('finish', {})]))
            replies = replies_of(served)
            self.assertEqual([row['id'] for row in replies], [0, 1, 2, 3, 4, 5, 6])
            for index in (2, 4, 5):
                self.assertTrue(replies[index]['result']['isError'])
                self.assertEqual(value_of(replies[index]), route_refusal('cover', COVER_ROUTES, 1024 if index == 2 else 1023))
            self.assertTrue(value_of(replies[3])['ok'])
            self.assertEqual(value_of(replies[3])['turns_remaining'], 1023)
            self.assertTrue(value_of(replies[6])['ok'])
            self.assertEqual(value_of(replies[6])['turns_remaining'], 1022)
            self.assertIn('headgasket: 3 remove calls named a route the part does not have; they were refused and not '
                          'recorded', served.stderr.decode())
            # Not recorded: the record holds the two calls that reached the game.
            record = json.loads((out / 'run.json').read_bytes())
            self.assertEqual([row['name'] for row in record['actions']], ['look', 'finish'])
            self.assertTrue(record['finished'])
            self.assertEqual(len((out / 'actions.jsonl').read_bytes().splitlines()), 2)
            verified = json.loads(run('verify', '--run', str(out)).stdout)
            self.assertTrue(verified['ok'] and verified['checks']['exact_replay'] and verified['checks']['finish_record_json'])
            self.assertTrue(json.loads(run('validate', str(out)).stdout)['ok'])

    def test_calls_the_game_refuses_safely_reach_it(self):
        call = {'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call',
                'params': {'name': 'remove', 'arguments': {'part_id': 'cover', 'route_id': 'no-such-route'}}}
        # Before the client is initialized the server refuses every call itself.
        early = (json.dumps(call) + '\n').encode()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            calls = [('remove', {'part_id': 'nothing', 'route_id': 'no-such-route'}),  # unknown part
                     ('remove', {'part_id': 'cover', 'route_id': None}),  # null: the schema refuses it
                     ('remove', {'part_id': 'cover'}),  # no route_id
                     ('remove', {'part_id': 'cover', 'route_id': COVER_ROUTES[0]}),  # its route, still blocked
                     ('remove', {'part_id': 'block', 'route_id': 'no-such-route'})]  # stays for the job
            served = run('serve', '--variant', 'V1', '--out', str(out), stdin=early + session(calls))
            replies = replies_of(served)
            self.assertEqual(replies[0], {'jsonrpc': '2.0', 'id': 9, 'error': {'code': -32602, 'message': 'Invalid request'}})
            self.assertEqual([row['id'] for row in replies], [9, 0, 1, 2, 3, 4, 5, 6])
            refusals = [value_of(reply)['refusal'] for reply in replies[3:]]
            self.assertEqual(len(refusals), 5)
            self.assertFalse(any('its routes are' in text for text in refusals), refusals)
            self.assertIn('Unknown component identifier', refusals[0])
            self.assertNotIn('named a route', served.stderr.decode())
            record = json.loads((out / 'run.json').read_bytes())
            self.assertEqual([row['input'] for row in record['actions']], [arguments for _, arguments in calls])
            self.assertEqual([row['result']['refusal'] for row in record['actions']], refusals)

    def test_a_published_record_with_such_calls_added_is_served_unchanged(self):
        # The calls of runs/family/V1-correct with refused calls added: the S1 call before
        # call 84 (the same part with its own route, 'unthread'), two at the start, and two
        # after call 246, where the new gasket (stock label stock_1582134695db, body
        # gasket_new) is installed in place of the old one. The stock label is resolved as
        # the game resolves it; the body id is unknown to the game, but the scoring step
        # reads a refused call's part_id as given and would fail on it. Takes about a minute.
        published = ROOT.parent / 'runs' / 'family' / 'V1-correct'
        calls = [(row['name'], row['input']) for row in json.loads((published / 'run.json').read_bytes())['actions']]
        self.assertEqual(calls[83], ('remove', {'part_id': 'ignition_wire_stay_bolt', 'route_id': 'unthread'}))
        self.assertEqual(calls[245], ('install', {'orientation': 'up', 'part_id': 'stock_1582134695db'}))
        injected = {0: [('remove', {'part_id': 'cover', 'route_id': 'no-such-route'}),
                        ('remove', {'part_id': 'cover', 'route_id': 7})],
                    83: [('remove', {'part_id': 'ignition_wire_stay_bolt', 'route_id': 'outward-unthread'})],
                    246: [('remove', {'part_id': 'stock_1582134695db', 'route_id': 'no-such-route'}),
                          ('remove', {'part_id': 'gasket_new', 'route_id': 'no-such-route'})]}
        sequence, expected = [], {}
        for index, item in enumerate(calls + [None]):
            for extra in injected.get(index, []):
                part = extra[1]['part_id']
                routes = {'cover': COVER_ROUTES, 'ignition_wire_stay_bolt': ['unthread']}.get(part, ['lift-after-head'])
                expected[len(sequence)] = route_refusal(part, routes, 1024 - index)
                sequence.append(extra)
            if item is not None:
                sequence.append(item)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'run'
            served = run('serve', '--variant', 'V1', '--out', str(out), stdin=session(sequence))
            replies = replies_of(served)[2:]  # after initialize and tools/list
            self.assertEqual([reply['id'] for reply in replies], list(range(2, len(sequence) + 2)))
            for position, reply in enumerate(replies):
                if position in expected:
                    self.assertEqual(value_of(reply), expected[position])
                else:
                    self.assertNotIn('error', reply)
            self.assertIn('headgasket: 5 remove calls', served.stderr.decode())
            for name in ('run.json', 'actions.jsonl'):
                self.assertEqual((out / name).read_bytes(), (published / name).read_bytes(), name)

    def test_no_published_call_names_a_route_its_part_does_not_have(self):
        # Every remove with a route_id in the published records names a route of the
        # removal-policy part it stands for, so the launcher hands every published call on.
        checked = 0
        for path in sorted((ROOT.parent / 'runs').glob('*/*/run.json')):
            record = json.loads(path.read_bytes())
            parts = {part['id']: part for part in record['config']['geometry']['parts']}
            routes = {row['id']: [item['id'] for item in row['routes']]
                      for row in record['config']['benchmark_removal']['policy']['parts']}
            replaced = record['final_state']['benchmark_removal']['replacements']
            resolved = {row['seq']: row['input'] for row in record['final_state']['action_history']}
            for row in record['actions']:
                if row['name'] != 'remove' or 'route_id' not in (row['input'] or {}):
                    continue
                self.assertTrue(row['result']['ok'], (path, row['seq']))
                body = resolved[row['seq']]['part_id']
                sources = {parts[body].get('l1_body_id')} | {source for source, new in replaced.items() if new == body}
                for source in sources - {None}:
                    self.assertIn(row['input']['route_id'], routes[source], (path, row['seq']))
                checked += 1
        self.assertEqual(checked, 14 * 51)


if __name__ == '__main__':
    unittest.main()
