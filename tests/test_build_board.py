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

    def check_toolsenabled_rows(self, board):
        """The rows of the runs made by ToolsEnabled, whatever submissions the board also holds."""
        self.assertEqual(board['fields'], list(build_board.FIELDS))
        ours = [r for r in board['rows'] if not r['name'].startswith('submitted/')]
        rows = {r['name']: r for r in ours}
        self.assertEqual(set(rows), {'reference/V1-amended', 'exploratory/gpt-6.1-sol',
                                     'exploratory/gpt-6-astra', 'exploratory/gpt-6-luna',
                                     'exploratory/claude-haiku-5-5-proxy-r1', 'exploratory/claude-haiku-5-5-proxy-r2',
                                     'exploratory/claude-haiku-5-5-proxy-r3'})
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
                    'exploratory/claude-haiku-5-5-proxy-r1': (14, 0.388889, 0, 3228, 13952)}
        for name, values in expected.items():
            r = rows[name]
            self.assertEqual((r['points'], r['s_partial'], r['s_full'], r['penalty_s'], r['productive_s']), values)
        self.assertEqual([r['name'] for r in ours],
                         ['reference/V1-amended', 'exploratory/gpt-6-astra', 'exploratory/claude-haiku-5-5-proxy-r1',
                          'exploratory/gpt-6-luna', 'exploratory/claude-haiku-5-5-proxy-r2', 'exploratory/claude-haiku-5-5-proxy-r3',
                          'exploratory/gpt-6.1-sol'])
        # Accepted submissions, if any, are listed as submitted runs.
        for r in board['rows']:
            if r['name'].startswith('submitted/'):
                self.assertIs(r['exploratory'], False)
                self.assertTrue(r['source'].startswith('submitted by '))

    def test_rows_from_the_repository_runs(self):
        self.check_toolsenabled_rows(json.loads(build_board.build(REPO / 'runs')))

    def test_an_accepted_submission_does_not_break_the_repository_test(self):
        # verification of F17 (side note): the push-time tests listed exactly the seven
        # ToolsEnabled rows, so the first merged submission would have turned them red.
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / 'runs'
            for part in ('reference', 'exploratory'):
                shutil.copytree(REPO / 'runs' / part, runs / part, ignore=shutil.ignore_patterns('actions.jsonl', 'report.json'))
            folder = runs / 'submitted' / '2026-10-14-alice-finish-only-v1'
            folder.mkdir(parents=True)
            (folder / 'run.json').write_text(json.dumps(fake_record('V1', 16, 0, 15000, 60)))
            (folder / 'SUBMISSION.json').write_text(json.dumps(
                {'model_label': 'model-a', 'client': 'client-a', 'variant': 'V1', 'date': '2026-10-14', 'submitter': 'alice'}))
            board = json.loads(build_board.build(runs))
            self.assertIn('submitted/2026-10-14-alice-finish-only-v1', [r['name'] for r in board['rows']])
            self.check_toolsenabled_rows(board)

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
                                     ('V1', 'exploratory/gpt-6-astra'), ('V1', 'exploratory/claude-haiku-5-5-proxy-r1'),
                                     ('V1', 'exploratory/gpt-6-luna'), ('V1', 'exploratory/claude-haiku-5-5-proxy-r2'),
                                     ('V1', 'exploratory/claude-haiku-5-5-proxy-r3'), ('V1', 'exploratory/gpt-6.1-sol'),
                                     ('V2', 'submitted/a-run'), ('V2', 'submitted/b-run'), ('V3', 'submitted/d-run')])
            submitted = [r for r in rows if r['name'].startswith('submitted/')]
            self.assertTrue(all(r['exploratory'] is False and r['source'] == 'submitted by tester' for r in submitted))
            out = Path(tmp) / 'board.json'
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out)]), 0)
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out), '--check']), 0)
            out.write_bytes(out.read_bytes().replace(b'"points": 2,', b'"points": 3,'))
            self.assertEqual(build_board.main(['--runs', str(runs), '--out', str(out), '--check']), 1)

    def test_links_stray_files_and_odd_names_under_submitted_are_refused(self):
        # redteam F2: a folder whose name has a space, or a link, skipped the pull-request
        # validator while build_board.py still put it on the board.
        record = fake_record('V1', 18, 1, 13630, 0)
        declaration = {'model_label': 'model-x', 'client': 'client-x', 'variant': 'V1', 'date': '2026-11-01',
                       'submitter': 'tester'}
        for case in ('space', 'link', 'dot-link', 'stray-file', 'linked-record'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                runs = Path(tmp) / 'runs'
                for part in ('reference', 'exploratory'):
                    shutil.copytree(REPO / 'runs' / part, runs / part,
                                    ignore=shutil.ignore_patterns('actions.jsonl', 'report.json'))
                submitted = runs / 'submitted'
                real = submitted / ('x y' if case == 'space' else 'real-run')
                real.mkdir(parents=True)
                (real / 'run.json').write_text(json.dumps(record))
                (real / 'SUBMISSION.json').write_text(json.dumps(declaration))
                if case == 'link':
                    (submitted / 'gpt-7-ultra-r1').symlink_to('real-run')
                elif case == 'dot-link':
                    (submitted / 'gpt-7-ultra-r1').symlink_to('.')
                elif case == 'stray-file':
                    (submitted / 'CLAIM.md').write_text('18/18')
                elif case == 'linked-record':
                    (real / 'run.json').unlink()
                    (real / 'run.json').symlink_to(Path(tmp) / 'elsewhere.json')
                    (Path(tmp) / 'elsewhere.json').write_text(json.dumps(record))
                with self.assertRaises(SystemExit):
                    build_board.build(runs)

    def test_an_unknown_exploratory_run_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / 'runs'
            for part in ('reference', 'exploratory'):
                shutil.copytree(REPO / 'runs' / part, runs / part, ignore=shutil.ignore_patterns('actions.jsonl', 'report.json'))
            (runs / 'exploratory' / 'not-a-known-run').mkdir()
            with self.assertRaises(SystemExit) as caught:
                build_board.build(runs)
            self.assertIn('not-a-known-run', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
