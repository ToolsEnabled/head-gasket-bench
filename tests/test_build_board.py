"""Tests for tools/build_board.py: content, order, determinism and --check."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import build_board  # noqa: E402


def fake_record(variant, points, s_full, productive, penalty):
    s_partial = 0.5 * points / 18 + 0.5 * s_full
    return {'config': {'variant_id': variant},
            'score': {'primary_score': {'points_earned': points, 'S_partial': s_partial, 'S_full': s_full},
                      'human_time': {'productive_seconds': productive, 'penalty_seconds': penalty}}}


class BuildBoardTests(unittest.TestCase):
    def test_committed_board_is_current(self):
        done = subprocess.run([sys.executable, '-B', str(REPO / 'tools' / 'build_board.py'), '--check'],
                              cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_rows_from_the_repository_runs(self):
        board = json.loads(build_board.build(REPO / 'runs'))
        self.assertEqual(board['fields'], list(build_board.FIELDS))
        rows = {r['name']: r for r in board['rows']}
        self.assertEqual(set(rows), {'reference/V1-amended', 'exploratory/gpt-6.1-sol',
                                     'exploratory/gpt-6-astra', 'exploratory/gpt-6-luna',
                                     'exploratory/claude-haiku-5-5-r1', 'exploratory/claude-haiku-5-5-r2',
                                     'exploratory/claude-haiku-5-5-r3'})
        for r in rows.values():
            self.assertEqual(tuple(r), build_board.FIELDS)
            self.assertTrue(r['exploratory'])
            self.assertEqual(r['source'], 'run by ToolsEnabled')
            self.assertEqual(r['variant'], 'V1')
        # The paper's Table 1 and Appendix F.
        expected = {'reference/V1-amended': (18, 1.0, 1, 0, 13630),
                    'exploratory/gpt-6-astra': (15, 0.416667, 0, 1404, 16190),
                    'exploratory/gpt-6-luna': (13, 0.361111, 0, 14970, 15230),
                    'exploratory/gpt-6.1-sol': (3, 0.083333, 0, 12012, 13280),
                    'exploratory/claude-haiku-5-5-r1': (0, 0.0, 0, 978, 1280)}
        for name, values in expected.items():
            r = rows[name]
            self.assertEqual((r['points'], r['s_partial'], r['s_full'], r['penalty_s'], r['productive_s']), values)
        self.assertEqual([r['name'] for r in board['rows']],
                         ['reference/V1-amended', 'exploratory/gpt-6-astra', 'exploratory/gpt-6-luna', 'exploratory/gpt-6.1-sol',
                          'exploratory/claude-haiku-5-5-r1', 'exploratory/claude-haiku-5-5-r2', 'exploratory/claude-haiku-5-5-r3'])

    def test_submissions_sorted_by_variant_then_score_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / 'runs'
            for part in ('reference', 'exploratory'):
                shutil.copytree(REPO / 'runs' / part, runs / part, ignore=shutil.ignore_patterns('actions.jsonl', 'report.json'))
            submissions = {'b-run': ('V2', 12, 0, 14000, 300), 'a-run': ('V2', 12, 0, 13900, 100),
                           'c-run': ('V1', 18, 1, 13630, 0), 'd-run': ('V3', 2, 0, 9000, 9000)}
            for name, (variant, points, s_full, productive, penalty) in submissions.items():
                folder = runs / 'submitted' / name
                folder.mkdir(parents=True)
                (folder / 'run.json').write_text(json.dumps(fake_record(variant, points, s_full, productive, penalty)))
                (folder / 'SUBMISSION.json').write_text(json.dumps(
                    {'model_label': 'model-' + name, 'client': 'client-x', 'variant': variant,
                     'date': '2026-11-01', 'submitter': 'tester'}))
            first = build_board.build(runs)
            self.assertEqual(first, build_board.build(runs))
            rows = json.loads(first)['rows']
            order = [(r['variant'], r['name']) for r in rows]
            self.assertEqual(order, [('V1', 'reference/V1-amended'), ('V1', 'submitted/c-run'),
                                     ('V1', 'exploratory/gpt-6-astra'), ('V1', 'exploratory/gpt-6-luna'),
                                     ('V1', 'exploratory/gpt-6.1-sol'), ('V1', 'exploratory/claude-haiku-5-5-r1'),
                                     ('V1', 'exploratory/claude-haiku-5-5-r2'), ('V1', 'exploratory/claude-haiku-5-5-r3'),
                                     ('V2', 'submitted/a-run'),
                                     ('V2', 'submitted/b-run'), ('V3', 'submitted/d-run')])
            submitted = [r for r in rows if r['name'].startswith('submitted/')]
            self.assertTrue(all(r['exploratory'] is False and r['source'] == 'submitted by tester' for r in submitted))
            out = Path(tmp) / 'board.json'
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out)]), 0)
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out), '--check']), 0)
            out.write_bytes(out.read_bytes().replace(b'"points": 2,', b'"points": 3,'))
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out), '--check']), 1)


if __name__ == '__main__':
    unittest.main()
