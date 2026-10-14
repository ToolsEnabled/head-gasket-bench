"""Tests for tools/check_pr_scope.py and the trust boundary of the pull-request workflow.

Each case builds a small git repository with a base branch and a pull-request branch and
runs the check the way the workflow does (from the base checkout, on git data only).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'tools' / 'check_pr_scope.py'
WORKFLOW = REPO / '.github' / 'workflows' / 'validate.yml'
RECORD = {'environment_source': {'interpreter': {'implementation': 'cpython', 'version': [3, 12, 5], 'cache_tag': 'cpython-312'}}}


def git(repo, *args):
    return subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@example.invalid', '-c',
                           'commit.gpgsign=false', *args], cwd=repo, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.decode()


def write(repo, path, text):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        write(self.repo, 'README.md', 'readme\n')
        write(self.repo, 'tools/build_board.py', 'print(1)\n')
        write(self.repo, 'runs/family/V1-correct/run.json', '{}\n')
        write(self.repo, 'leaderboard/board.json', '{}\n')
        write(self.repo, 'runs/submitted/2026-11-01-existing-v1/run.json', json.dumps(RECORD))
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'base')
        git(self.repo, 'checkout', '-q', '-b', 'pr')

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'pr')
        out = Path(self.tmp.name) / 'github-output'
        out.write_text('')
        done = subprocess.run([sys.executable, '-B', str(SCRIPT), '--base', 'main', '--head', 'pr', '--github-output', str(out)],
                              cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return done.returncode, done.stdout.decode(), out.read_text()

    def add_submission(self, name, record=RECORD):
        write(self.repo, f'runs/submitted/{name}/run.json', json.dumps(record))
        write(self.repo, f'runs/submitted/{name}/SUBMISSION.json', '{}\n')

    def assert_refused(self, text):
        code, stdout, output = self.check()
        self.assertEqual(code, 1, stdout)
        self.assertIn(text, stdout)
        self.assertEqual(output, '')

    def test_a_new_submission_and_the_board(self):
        self.add_submission('2026-11-02-model-x-v1')
        write(self.repo, 'leaderboard/board.json', '{"rows": 1}\n')
        code, stdout, output = self.check()
        self.assertEqual(code, 0, stdout)
        matrix = json.loads(re.search(r'^matrix=(.*)$', output, re.M).group(1))
        self.assertEqual(matrix, {'include': [{'name': '2026-11-02-model-x-v1', 'python': '3.12.5'}]})
        self.assertIn('any=true', output)

    def test_an_unreadable_record_gets_the_default_python(self):
        self.add_submission('2026-11-02-model-x-v1', record={'environment_source': {'interpreter': {'version': [3, 13, 0]}}})
        code, _, output = self.check()
        self.assertEqual(code, 0)
        self.assertIn('"python": "3.12.3"', output)

    def test_a_board_only_change_is_checked_and_lists_nothing(self):
        write(self.repo, 'leaderboard/board.json', '{"rows": "hand-made"}\n')
        code, stdout, output = self.check()
        self.assertEqual(code, 0, stdout)
        self.assertIn('any=false', output)

    def test_a_folder_name_with_a_space(self):
        self.add_submission('x y')
        self.assert_refused('folder name')

    def test_a_folder_name_with_a_newline(self):
        self.add_submission('xyz\nabc')
        self.assert_refused('folder name')

    def test_a_linked_folder(self):
        os.symlink('2026-11-01-existing-v1', self.repo / 'runs' / 'submitted' / '2026-11-02-linked-v1')
        self.assert_refused('a submission is one folder')

    def test_a_linked_file_in_a_new_folder(self):
        self.add_submission('2026-11-02-model-x-v1')
        os.symlink('../../family/V1-correct/run.json', self.repo / 'runs' / 'submitted' / '2026-11-02-model-x-v1' / 'actions.jsonl')
        self.assert_refused('is a link or a submodule')

    def test_a_file_directly_under_submitted(self):
        write(self.repo, 'runs/submitted/CLAIM.md', '18/18\n')
        self.assert_refused('a submission is one folder')

    def test_a_nested_folder(self):
        write(self.repo, 'runs/submitted/2026-11-02-model-x-v1/extra/file.json', '{}\n')
        self.assert_refused('a submission is one folder')

    def test_code_and_published_records_are_outside_the_scope(self):
        self.add_submission('2026-11-02-model-x-v1')
        write(self.repo, 'tools/build_board.py', 'print(2)\n')
        self.assert_refused("'tools/build_board.py': outside")

    def test_a_published_record_is_outside_the_scope(self):
        write(self.repo, 'runs/family/V1-correct/run.json', '{"changed": true}\n')
        self.assert_refused("'runs/family/V1-correct/run.json': outside")

    def test_changing_an_existing_submission(self):
        write(self.repo, 'runs/submitted/2026-11-01-existing-v1/SUBMISSION.json', '{"submitter": "someone else"}\n')
        self.assert_refused('already on the base branch')

    def test_removing_an_existing_submission(self):
        git(self.repo, 'rm', '-q', '-r', 'runs/submitted/2026-11-01-existing-v1')
        self.assert_refused('removes a file of a submission')

    def test_a_code_change_is_not_a_submission(self):
        write(self.repo, 'tools/build_board.py', 'print(2)\n')
        write(self.repo, 'docs/notes.md', 'notes\n')
        code, stdout, output = self.check()
        self.assertEqual(code, 0, stdout)
        self.assertIn('Not a submission pull request', stdout)
        self.assertIn('kind=code', output)
        self.assertIn('any=false', output)

    def test_many_other_files_do_not_hide_a_submission(self):
        # verification of the paths filter: GitHub matched it against only the first
        # 3,000 changed files. The check now runs on every pull request and reads every path.
        for index in range(40):
            write(self.repo, f'docs/f{index:04d}.md', 'x\n')
        self.add_submission('2026-11-02-forged-v1')
        write(self.repo, 'leaderboard/board.json', '{"rows": "hand-made"}\n')
        self.assert_refused("'docs/f0000.md': outside")

    def test_at_most_ten_submissions_per_pull_request(self):
        for index in range(11):
            self.add_submission(f'2026-11-02-model-x-v1-r{index:02d}')
        self.assert_refused('at most 10 per pull request')

    def test_ten_submissions_are_listed(self):
        for index in range(10):
            self.add_submission(f'2026-11-02-model-x-v1-r{index:02d}')
        code, stdout, output = self.check()
        self.assertEqual(code, 0, stdout)
        self.assertEqual(len(json.loads(re.search(r'^matrix=(.*)$', output, re.M).group(1))['include']), 10)

    def test_a_pull_request_behind_main_is_checked_against_the_merge_result(self):
        # main moved on (an unrelated change) after the pull request branched: only the
        # pull request's own change is in the merge result.
        self.add_submission('2026-11-02-model-x-v1')
        write(self.repo, 'leaderboard/board.json', '{"rows": 1}\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'pr')
        git(self.repo, 'checkout', '-q', 'main')
        write(self.repo, 'README.md', 'readme, edited on main\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'main moves on')
        git(self.repo, 'checkout', '-q', 'pr')
        code, stdout, output = self.check()
        self.assertEqual(code, 0, stdout)
        self.assertIn('"name": "2026-11-02-model-x-v1"', output)

    def test_a_pull_request_that_does_not_merge_cleanly(self):
        write(self.repo, 'leaderboard/board.json', '{"rows": "pr"}\n')
        self.add_submission('2026-11-02-model-x-v1')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'pr')
        git(self.repo, 'checkout', '-q', 'main')
        write(self.repo, 'leaderboard/board.json', '{"rows": "main"}\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'main moves on')
        git(self.repo, 'checkout', '-q', 'pr')
        self.assert_refused('does not merge cleanly')

    def criss_cross(self):
        """main holds a merge commit whose two parents are not ancestors of each other
        (GitHub's merge button makes one for a pull request branched from an older main):
        alice's submission came in on one side, bob's on the other. The attacker branches
        from bob's side and records alice's side as merged with -s ours, dropping alice."""
        git(self.repo, 'checkout', '-q', 'main')
        git(self.repo, 'checkout', '-q', '-b', 'bob')
        self.add_submission('2026-11-02-bob-v1')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'bob')
        git(self.repo, 'checkout', '-q', 'main')
        self.add_submission('2026-11-02-alice-v1')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'alice')
        git(self.repo, 'merge', '-q', '--no-ff', '--no-edit', 'bob')
        git(self.repo, 'branch', '-q', '-D', 'pr')
        git(self.repo, 'checkout', '-q', '-b', 'pr', 'bob')
        git(self.repo, 'merge', '-q', '-s', 'ours', '--no-edit', 'main~1')
        self.add_submission('2026-11-03-mallory-v1')
        write(self.repo, 'leaderboard/board.json', '{"rows": "without alice"}\n')

    def test_a_criss_cross_history_is_refused(self):
        # verification of F17: the diff against one merge base showed only the new folder,
        # and merging deleted alice's accepted submission.
        self.criss_cross()
        bases = git(self.repo, 'merge-base', '--all', 'main', 'pr').split()
        self.assertEqual(len(bases), 2)
        self.assert_refused('2 merge bases')

    def test_the_merge_result_shows_what_a_criss_cross_pull_request_removes(self):
        sys.path.insert(0, str(REPO / 'tools'))
        import check_pr_scope
        self.criss_cross()
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'pr')
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with unittest.mock.patch.object(check_pr_scope, 'merge_result', side_effect=lambda base, head: git(
                    self.repo, 'merge-tree', '--write-tree', '--no-messages', base, head).split()[0]):
                rows = check_pr_scope.changes('main', 'pr')
        finally:
            os.chdir(cwd)
        removed = [path for status, _mode, path in rows if status == 'D']
        self.assertIn('runs/submitted/2026-11-02-alice-v1/run.json', removed)

    def test_an_unrelated_history_is_refused(self):
        git(self.repo, 'checkout', '-q', '--orphan', 'other')
        git(self.repo, 'rm', '-q', '-r', '--cached', '.')
        self.add_submission('2026-11-02-model-x-v1')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'unrelated')
        git(self.repo, 'branch', '-q', '-D', 'pr')
        git(self.repo, 'branch', '-q', '-m', 'other', 'pr')
        self.assert_refused('0 merge bases')


class WorkflowTrustBoundaryTests(unittest.TestCase):
    """The pull-request jobs run the base branch's code and read the pull request as data."""

    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_triggers(self):
        # Every pull request, with no paths filter: GitHub matches a filter against only the
        # first 3,000 changed files, and a required check that a filter skips stays pending.
        self.assertRegex(self.text, r"(?m)^on:\n  pull_request_target:\n  push:\n    branches: \[main\]\n")
        self.assertNotRegex(self.text, r'(?m)^  pull_request:')
        self.assertNotRegex(self.text, r'(?m)^\s+paths(-ignore)?:')

    def test_the_verdict_job_sums_up_the_others(self):
        # A skipped job counts as passed in a required check: the verdict runs always and
        # fails unless every job that applies passed.
        start = self.text.index('\n  verdict:\n')
        block = self.text[start:self.text.index('\n  tests:\n')]
        self.assertIn('needs: [changed, submission, board]', block)
        self.assertIn("if: always() && github.event_name == 'pull_request_target'", block)
        for line in ('test "$CHANGED" = success', 'test "$KIND" = code || test "$BOARD" = success',
                     'test "$KIND" = code || test "$ANY" != true || test "$SUBMISSION" = success'):
            self.assertIn(line, block)
        self.assertIn("needs.changed.outputs.kind == 'submission'", self.text)

    def test_read_only_token_no_secrets_no_kept_credentials(self):
        self.assertRegex(self.text, r'(?m)^permissions:\n  contents: read\n\n')
        self.assertNotIn('secrets.', self.text)
        self.assertNotIn('write', re.sub(r'(?m)^\s*#.*$', '', self.text))
        checkouts = self.text.count('uses: actions/checkout@')
        self.assertEqual(self.text.count('persist-credentials: false'), checkouts)

    def test_the_pull_request_is_only_checked_out_under_pr(self):
        heads = [m.start() for m in re.finditer(r'ref: \$\{\{ github\.event\.pull_request\.head\.sha \}\}', self.text)]
        self.assertEqual(len(heads), 2)
        for start in heads:
            self.assertRegex(self.text[start:start + 120], r'\n\s+path: pr\n')
        self.assertEqual(self.text.count('ref: ${{ github.sha }}'), 3)

    def test_every_command_comes_from_the_base_checkout(self):
        runs = re.findall(r'(?m)^\s+run: (.*)$', self.text) + re.findall(r'(?ms)run: \|\n(.*?)\n\n', self.text)
        commands = [line.strip() for block in runs for line in block.splitlines()
                    if line.strip() and not line.strip().startswith('#')]
        self.assertTrue(commands)
        for command in commands:
            # The pull request's files appear only as arguments after a base-branch tool.
            self.assertFalse(re.match(r'(\S*/)?pr/', command), command)
            self.assertNotRegex(command, r'(?:python3?|bash|sh|source|\.)\s+(?:-\S+\s+)*["\']?pr/', command)
        self.assertNotIn('${{ github.event.pull_request.title', self.text)
        self.assertNotIn('${{ github.event.pull_request.body', self.text)
        self.assertNotIn('${{ github.head_ref', self.text)


if __name__ == '__main__':
    unittest.main()
