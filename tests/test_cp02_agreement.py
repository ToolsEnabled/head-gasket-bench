"""CP02: the environment and the independent scorer decide refused attempts alike.

The paper defines CP02 (Appendix C): "Disassembly followed the documented removal
policy. Any refused removal attempt of a part that was still blocked or still
attached fails CP02". Each case below replays the calls of the published scripted
record runs/family/V1-correct through the pinned environment with a few calls
injected, then scores the new record with scorer/hgj_scorer.py. For every case the
refused calls the environment counts against CP02 (its CP02 evidence) and the ones
the scorer counts must be the same, CP02 must pass or fail in both as expected, and
the primary comparison must agree. Building and scoring the records takes a few
minutes.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV = REPO / 'env'
SCORER = REPO / 'scorer'
SCRIPTED = REPO / 'runs' / 'family' / 'V1-correct' / 'run.json'

# Run in env/ as a child process: replays the first `until` scripted calls (all when
# null) with the injected calls added after the scripted call numbers given, through
# the pinned environment, and writes one record per case.
MAKE = r"""
import importlib, json, sys
from pathlib import Path
from headgasket import cli
pins = cli.load_pins()
runtime = cli.runtime_for(pins)
base = [(row['name'], row['input']) for row in json.loads(Path(sys.argv[1]).read_bytes())['actions']]
cases = json.loads(Path(sys.argv[2]).read_text())
out = Path(sys.argv[3])
with runtime.active():
    game = importlib.import_module('hgj.game')
    item = pins['configurations']['V1']
    config, _ = cli.load_config(cli.ROOT / item['path'], item['sha256'])
    for name, case in cases.items():
        calls = list(base[:case['until']] if case['until'] is not None else base)
        for after, injected in sorted(case['inject'], key=lambda row: -row[0]):
            calls[after:after] = [(tool, arguments) for tool, arguments, _ in injected]
        g = game.Game(config, source_runtime=runtime)
        for tool, arguments in calls:
            g.call(tool, arguments)
        (out / (name + '.json')).write_bytes(cli.canonical(g.export()))
"""

# Run as a child process: scores each record with the repository scorer.
SCORE = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import hgj_scorer
result = {}
for path in sys.argv[2:]:
    assessment = hgj_scorer.assess(hgj_scorer.load_record(path), 'amendment-2-20261010', None)
    cp02 = next(row for row in assessment['primary_score']['checkpoints'] if row['id'] == 'CP02')
    result[Path(path).stem] = {
        'passed': cp02['passed'], 'primary': assessment['primary_comparison']['status'],
        'counted': sorted(row['sequence'] for row in assessment['source_removal']['disassembly_invalid_attempts']
                          if not row['ok'])}
print(json.dumps(result))
"""


def call(tool, arguments, counts=None):
    """An injected call: counts is True for a refusal that fails CP02, False for a
    refusal that does not, and None for a call that must succeed."""
    return [tool, arguments, counts]


def remove(part, counts):
    return call('remove', {'part_id': part}, counts)


LOOSEN_CB01 = call('torque', {'part_id': 'cb01', 'mode': 'loosen', 'angle_deg': -120})

# Scripted call numbers of runs/family/V1-correct used below: 11 inspect belt, 13 the
# first timing check, 74 cover bolt cb01 removed (with its grommet cw01), 118 valve cover
# removed, 246 new gasket installed after replace(gasket_old -> stock), 247 head installed.
CASES = {
    'refusals_that_do_not_count': {'until': None, 'passes': True, 'inject': [
        # (a) refused prepare_condition
        (11, [call('prepare_condition', {'condition_id': 'timing_marks_recorded'}, False),
              call('prepare_condition', {'condition_id': 'no_such_condition'}, False)]),
        # (b) refused release_attachment
        (13, [call('release_attachment', {'release_id': 'thread:cover_fastener_05'}, False),
              call('release_attachment', {'release_id': 'thread:bolt_01:block_casting'}, False),
              call('release_attachment', {'release_id': 'no-such-release'}, False),
              # (d) a refused remove for a reason other than a blocked or attached part
              remove('no_such_part', False),
              remove('stock_1582134695db', False)]),
        (74, [remove('cw01', False)]),            # already off, with its carrier cb01
        (118, [remove('cover', False)]),          # already removed
        (246, [remove('gasket_old', False)]),     # the original, after replace
        # The environment reads a refused call's part as given, so a refusal that names a
        # stock label is not counted even when that part is blocked (here by the head);
        # the scorer follows the environment.
        (247, [remove('stock_1582134695db', False)])]},
    'refusals_that_count': {'until': 120, 'passes': False, 'inject': [
        # (c) a part the removal policy still blocks, one that comes off only with its
        # assembly, one retained for the job; (e) a head bolt still threaded, and the valve
        # cover while its bolts are still threaded
        (13, [remove('head', True), remove('cw01', True), remove('alternator_bearing_cover', True),
              remove('hb01', True), remove('cover', True)])]},
    # (e) a scored bolt refitted and still engaged: its route is open again (the thread
    # release is still recorded), so the refusal counts, as in the environment.
    'refitted_bolt_still_engaged': {'until': 120, 'passes': False, 'inject': [
        (74, [call('install', {'part_id': 'cb01'}), remove('cb01', True)] + [LOOSEN_CB01] * 6
             + [call('remove', {'part_id': 'cb01'})])]},
    'refitted_bolt_without_refusal': {'until': 120, 'passes': True, 'inject': [
        (74, [call('install', {'part_id': 'cb01'})] + [LOOSEN_CB01] * 6 + [call('remove', {'part_id': 'cb01'})])]},
}


def child(code, args, cwd):
    done = subprocess.run([sys.executable, '-B', '-c', code, *args], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=3600, check=False)
    if done.returncode != 0:
        raise AssertionError(done.stderr.decode())
    return done.stdout


class CP02AgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        (folder / 'cases.json').write_text(json.dumps(CASES))
        child(MAKE, [str(SCRIPTED), str(folder / 'cases.json'), str(folder)], ENV)
        cls.records = {name: json.loads((folder / (name + '.json')).read_bytes()) for name in CASES}
        cls.scores = json.loads(child(SCORE, [str(SCORER), *(str(folder / (name + '.json')) for name in CASES)],
                                      SCORER))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_environment_and_scorer_count_the_same_refusals(self):
        for name, case in CASES.items():
            with self.subTest(name):
                record, score = self.records[name], self.scores[name]
                # Where each injected call landed in the record.
                rows, offset = [], 0
                for after, injected in sorted(case['inject'], key=lambda row: row[0]):
                    for k, (tool, arguments, counts) in enumerate(injected):
                        row = record['actions'][after + offset + k]
                        self.assertEqual([row['name'], row['input']], [tool, arguments])
                        self.assertEqual(row['result']['ok'], counts is None, (name, row['seq'], row['result']))
                        rows.append((row['seq'], counts))
                    offset += len(injected)
                expected = sorted(seq for seq, counts in rows if counts)
                cp02 = next(row for row in record['score']['primary_score']['checkpoints'] if row['id'] == 'CP02')
                refused = {row['seq'] for row in record['actions'] if row['result']['ok'] is False}
                environment_counted = sorted(set(cp02['evidence_sequences']) & refused)
                self.assertEqual(environment_counted, expected)
                self.assertEqual(score['counted'], expected)
                self.assertEqual(cp02['passed'], case['passes'])
                self.assertEqual(score['passed'], case['passes'])
                self.assertEqual(score['primary'], 'agreement')


if __name__ == '__main__':
    unittest.main()
