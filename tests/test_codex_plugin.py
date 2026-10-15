"""Real plugin entry behavior; no provider calls, scientific pins unchanged."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('codex_mcp', ROOT / 'tools' / 'codex-mcp.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class CodexPluginTests(unittest.TestCase):
    def test_missing_relative_and_overlapping_state_refuse_without_cli(self):
        for value in ['', 'relative', str(ROOT), str(ROOT / 'records'), str(ROOT.parent)]:
            with self.subTest(value=value), mock.patch('headgasket.cli.main', side_effect=AssertionError('must not invoke CLI')):
                with self.assertRaises(ValueError):
                    entry.serve({'HEADGASKET_RUN_DIR': value})

    def test_external_spaced_path_and_variant_reach_canonical_cli(self):
        run = str(Path(tempfile.mkdtemp(prefix='hgb codex ')) / 'new record')
        with mock.patch('headgasket.cli.main', return_value=7) as cli:
            self.assertEqual(entry.serve({'HEADGASKET_RUN_DIR': run, 'HEADGASKET_VARIANT': 'V3'}), 7)
            self.assertEqual(cli.call_args.args[0], ['serve', '--variant', 'V3', '--out', run])

    def test_real_wire_look_records_one_action_and_replay_verifies(self):
        run = Path(tempfile.mkdtemp(prefix='hgb-codex-wire-')) / 'run'
        env = dict(os.environ, HEADGASKET_RUN_DIR=str(run), HEADGASKET_VARIANT='V1')
        requests = [
            {'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':1,'method':'tools/list'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'look','arguments':{}}},
        ]
        result = subprocess.run([sys.executable, '-B', str(ROOT/'tools/codex-mcp.py')], env=env, input=''.join(json.dumps(x)+'\n' for x in requests), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        replies=[json.loads(x) for x in result.stdout.splitlines()]
        self.assertEqual(replies[0]['result']['serverInfo']['name'], 'headgasket')
        self.assertEqual(len(replies[1]['result']['tools']),18)
        self.assertFalse(replies[2]['result'].get('isError',False))
        record=json.loads((run/'run.json').read_text())
        self.assertEqual([x['name'] for x in record['actions']], ['look'])
        replay=subprocess.run([sys.executable,'-B',str(ROOT/'env/bin/headgasket-mcp'),'replay','--record',str(run/'run.json')],text=True,capture_output=True,timeout=30)
        self.assertEqual(replay.returncode,0,replay.stderr)


if __name__ == '__main__': unittest.main()
