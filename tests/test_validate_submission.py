"""Tests for tools/validate_submission.py.

One passing submission (a copy of the scripted V1-correct family record) and four
broken ones: a hash-chain break, a replay mismatch, a score mismatch and a secret.
The passing and score-mismatch cases replay the record (about a minute each).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / 'tools' / 'validate_submission.py'
SOURCE = REPO / 'runs' / 'family' / 'V1-correct'
sys.path.insert(0, str(REPO / 'tools'))
import validate_submission as validator  # noqa: E402

DECLARATION = {'model_label': 'scripted-control', 'client': 'scripted (no model)', 'variant': 'V1',
               'date': '2026-10-14', 'submitter': 'ToolsEnabled test suite',
               'notes': 'Validator test fixture: the scripted V1-correct family record.'}


def canonical(value):
    return validator.canonical(value)


def rewrite(folder, record):
    """Write a modified record back with a consistent journal and report."""
    raw = canonical(record)
    (folder / 'run.json').write_bytes(raw)
    (folder / 'actions.jsonl').write_bytes(b''.join(canonical(row) for row in record['actions']))
    report = json.loads((folder / 'report.json').read_bytes())
    report['run_sha256'] = hashlib.sha256(raw).hexdigest()
    (folder / 'report.json').write_bytes(canonical(report))


def run(folder):
    done = subprocess.run([sys.executable, '-B', str(VALIDATOR), str(folder)], cwd=REPO,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600, check=False)
    lines = done.stdout.decode().strip().splitlines()
    return done.returncode, lines


class ValidateSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.good = Path(cls.tmp.name) / 'good' / '2026-10-14-scripted-control-v1'
        cls.good.mkdir(parents=True)
        for name in ('run.json', 'actions.jsonl', 'report.json'):
            shutil.copyfile(SOURCE / name, cls.good / name)
        (cls.good / 'SUBMISSION.json').write_text(json.dumps(DECLARATION, indent=2) + '\n')
        validator.write_result(cls.good)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self, label):
        target = Path(self.tmp.name) / label / self.good.name
        shutil.copytree(self.good, target)
        return target

    def assert_fails(self, folder, check):
        code, lines = run(folder)
        self.assertEqual(code, 1, lines)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f'FAIL {folder}: {check}:'), lines)

    def test_passing_copy_of_the_v1_correct_family_record(self):
        code, lines = run(self.good)
        self.assertEqual(code, 0, lines)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f'PASS {self.good}: V1 18/18 S_partial 1.000000'), lines)

    def test_chain_break(self):
        folder = self.copy('chain')
        record = json.loads((folder / 'run.json').read_bytes())
        record['actions'][100]['previous_action_sha256'] = '0' * 64
        rewrite(folder, record)
        self.assert_fails(folder, 'chain')

    def test_replay_mismatch(self):
        # Change what the first action observed and re-link the chain, the journal and the
        # report so that every stdlib check passes; only the environment can tell.
        folder = self.copy('replay')
        record = json.loads((folder / 'run.json').read_bytes())
        actions = record['actions']
        actions[0]['human_time_charge']['base_seconds'] = actions[0]['human_time_charge'].get('base_seconds', 0) + 1
        for index in range(1, len(actions)):
            actions[index]['previous_action_sha256'] = validator.digest(actions[index - 1])
        rewrite(folder, record)
        self.assert_fails(folder, 'replay')

    def test_score_mismatch(self):
        folder = self.copy('score')
        text = (folder / 'RESULT.md').read_text()
        self.assertIn('| points | 18/18 |', text)
        (folder / 'RESULT.md').write_text(text.replace('| points | 18/18 |', '| points | 17/18 |'))
        self.assert_fails(folder, 'scorer')

    def test_secret(self):
        folder = self.copy('secret')
        declaration = dict(DECLARATION)
        # Key-shaped but fake; assembled at run time so no key-shaped literal is stored in the repository.
        declaration['notes'] = 'run with key ' + 'sk-' + 'proj-' + 'Q7xYv2' * 6
        (folder / 'SUBMISSION.json').write_text(json.dumps(declaration, indent=2) + '\n')
        self.assert_fails(folder, 'secrets')

    def test_personal_path(self):
        folder = self.copy('path')
        declaration = dict(DECLARATION)
        declaration['notes'] = 'record copied from ' + '/' + 'home/' + 'someone/runs/v1'
        (folder / 'SUBMISSION.json').write_text(json.dumps(declaration, indent=2) + '\n')
        self.assert_fails(folder, 'secrets')

    def test_size_and_extra_files(self):
        folder = self.copy('extra')
        (folder / 'notes.txt').write_text('extra')
        self.assert_fails(folder, 'files')


if __name__ == '__main__':
    unittest.main()
