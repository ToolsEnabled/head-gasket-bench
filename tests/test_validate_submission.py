"""Tests for tools/validate_submission.py.

The fixtures are fresh runs, not copies of published records (a copy is refused as a
duplicate): a short unfinished run and a finish-only run served through the real stdio
launcher, and the published V1-correct calls without the final timing check (16/18),
made with the pinned environment in a child process (the same bytes serve writes).
Building the fixtures and the passing cases replays and rescores records (about four
minutes in all).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
ENV = REPO / 'env'
LAUNCHER = ENV / 'bin' / 'headgasket-mcp'
VALIDATOR = REPO / 'tools' / 'validate_submission.py'
PUBLISHED = REPO / 'runs' / 'family' / 'V1-correct'
sys.path.insert(0, str(REPO / 'tools'))
import validate_submission as validator  # noqa: E402

DECLARATION = {'model_label': 'scripted-control', 'client': 'scripted (no model)', 'variant': 'V1',
               'date': '2026-10-14', 'submitter': 'ToolsEnabled test suite',
               'notes': 'Validator test fixture: a scripted run, no model.'}

# Runs in env/ as a child process: makes a record with the pinned environment, or prints
# the report.json envelopes the pinned report_for_run writes for a record.
HELPER = r'''
import importlib, json, sys
from pathlib import Path
from headgasket import cli
pins = cli.load_pins()
runtime = cli.runtime_for(pins)
with runtime.active():
    game = importlib.import_module('hgj.game')
    repair_report = importlib.import_module('hgj.repair_report')
    if sys.argv[1] == 'make':
        out = Path(sys.argv[2])
        calls = json.loads(Path(sys.argv[3]).read_text())
        item = pins['configurations']['V1']
        config, _ = cli.load_config(cli.ROOT / item['path'], item['sha256'])
        g = game.Game(config, source_runtime=runtime)
        for name, arguments in calls:
            g.call(name, arguments)
        record = g.export()
        reason = 'finished' if record['finished'] else 'input_ended_without_finish'
        out.mkdir(parents=True)
        (out / 'run.json').write_bytes(cli.canonical(record))
        (out / 'actions.jsonl').write_bytes(b''.join(cli.canonical(row) for row in record['actions']))
        (out / 'report.json').write_bytes(cli.canonical(repair_report.report_for_run(record, 1.5, terminal_reason=reason)))
    else:
        record = json.loads(Path(sys.argv[2]).read_bytes())
        reasons = ['finished'] if record['finished'] else ['running', 'input_ended_without_finish', 'interrupted',
                                                           'transport_error']
        print(json.dumps({r: repair_report.report_for_run(record, 2.25, terminal_reason=r) for r in reasons}))
'''


def canonical(value):
    return validator.canonical(value)


def helper(*args):
    code = 'import sys; sys.path.insert(0, ' + repr(str(ENV)) + ')\n' + HELPER
    done = subprocess.run([sys.executable, '-B', '-c', code, *args], cwd=ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=1800, check=False)
    if done.returncode != 0:
        raise AssertionError(done.stderr.decode())
    return done.stdout


def serve(out, calls):
    """A real stdio session through the launcher."""
    rows = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'}]
    rows += [{'jsonrpc': '2.0', 'id': i + 1, 'method': 'tools/call', 'params': {'name': n, 'arguments': a}}
             for i, (n, a) in enumerate(calls)]
    data = b''.join((json.dumps(row) + '\n').encode() for row in rows)
    done = subprocess.run([sys.executable, '-B', str(LAUNCHER), 'serve', '--variant', 'V1', '--out', str(out)],
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False)
    if done.returncode != 0:
        raise AssertionError(done.stderr.decode())


def submission(folder, declaration=DECLARATION):
    """Keep the three record files, add SUBMISSION.json and generate RESULT.md."""
    for name in ('launch.json', 'finish-record.json'):
        (folder / name).unlink(missing_ok=True)
    (folder / 'SUBMISSION.json').write_text(json.dumps(declaration, indent=2) + '\n')
    validator.write_result(folder)
    return folder


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


class DeterminedDisagreementTests(unittest.TestCase):
    """An unknown (null) independent value is not a disagreement; a determined one is."""

    def test_unknown_independent_value_is_not_compared(self):
        comparison = {'disagreements': [
            {'field': 'surface/cover_face/tube_seals_oiled', 'independent': None, 'producer': False}]}
        self.assertEqual(validator.determined_disagreements(comparison), [])

    def test_determined_disagreement_still_counts(self):
        row = {'field': 'human_time/penalty_seconds', 'independent': 30, 'producer': 60}
        comparison = {'disagreements': [row, {'field': 'x', 'independent': None, 'producer': True}]}
        self.assertEqual(validator.determined_disagreements(comparison), [row])

    def test_no_disagreements(self):
        self.assertEqual(validator.determined_disagreements({}), [])

    def test_the_independent_only_mistake_type_is_left_out(self):
        # A finished run without a final timing check: only the independent scorer has a
        # mistake type for it (the environment scores it in CP11).
        row = {'field': 'mistakes/by_type', 'independent': {'missed_lookup': 1, 'missing_timing_verification': 1},
               'producer': {'missed_lookup': 1}}
        self.assertEqual(validator.determined_disagreements({'disagreements': [row]}), [])

    def test_every_other_mistake_type_is_still_compared(self):
        row = {'field': 'mistakes/by_type', 'independent': {'missing_timing_verification': 1, 'wrong_order': 2},
               'producer': {'wrong_order': 1}}
        self.assertEqual(validator.determined_disagreements({'disagreements': [row]}), [row])

    def test_the_environment_never_produces_that_type(self):
        env_source = ''.join(path.read_text() for path in sorted((ENV / 'hgj').glob('*.py')))
        scorer_source = (REPO / 'scorer' / 'job_accuracy' / 'independent.py').read_text()
        for kind in validator.INDEPENDENT_ONLY_MISTAKE_TYPES:
            self.assertNotIn(kind, env_source)
            self.assertIn(f"'{kind}'", scorer_source)


class SharedCallsTests(unittest.TestCase):
    """shared_calls is the longest common subsequence of two call lists."""

    @staticmethod
    def longest_common_subsequence(a, b):
        previous = [0] * (len(b) + 1)
        for x in a:
            current = [0]
            for j, y in enumerate(b):
                current.append(previous[j] + 1 if x == y else max(previous[j + 1], current[j]))
            previous = current
        return previous[-1]

    def test_matches_the_textbook_algorithm(self):
        import random
        rng = random.Random(20261014)
        for _ in range(2000):
            a = [rng.choice('abcde') for _ in range(rng.randint(0, 25))]
            b = [rng.choice('abcdef') for _ in range(rng.randint(0, 25))]
            self.assertEqual(validator.shared_calls(a, b), self.longest_common_subsequence(a, b), (a, b))

    def test_near_copies_of_a_scripted_record_are_found_and_model_runs_are_not(self):
        scripted = [f'call-{i}' for i in range(436)]
        for mine in (['extra'] + scripted, scripted[:300], scripted + ['x'] * 600, scripted[:200] + ['y'] + scripted[201:]):
            match = ('runs/family/V1-wrong_timing', validator.shared_calls(mine, scripted), len(scripted))
            self.assertTrue(validator.near_copy(mine, match))
        # About half of the calls in common, the most any model run ToolsEnabled made reached.
        half = scripted[::2] + [f'model-{i}' for i in range(200)]
        self.assertFalse(validator.near_copy(half, ('x', validator.shared_calls(half, scripted), len(scripted))))
        # A short run is not flagged for a few common opening calls.
        short = scripted[:5]
        self.assertFalse(validator.near_copy(short, ('x', validator.shared_calls(short, scripted), len(scripted))))
        self.assertFalse(validator.near_copy(short, None))


class DeclarationAndScanTests(unittest.TestCase):
    def declaration(self, **changes):
        return json.dumps({**DECLARATION, **changes}).encode()

    def assert_refused(self, raw):
        with self.assertRaises(validator.Fail) as caught:
            validator.check_declaration(raw)
        self.assertEqual(caught.exception.check, 'declaration')

    def test_names_and_dates_are_matched_whole(self):
        self.assertIsNone(validator.NAME_RE.fullmatch('2026-10-14-model-v1\n'))
        self.assertIsNotNone(validator.NAME_RE.fullmatch('2026-10-14-model-v1'))
        for date in ('2026-10-14\n', '２０２６-１０-１４', '9999-99-99', '2026-02-30'):
            self.assert_refused(self.declaration(date=date))
        self.assertEqual(validator.check_declaration(self.declaration())['date'], '2026-10-14')

    def test_shown_values_are_plain_text(self):
        for key, value in (('model_label', 'x` [click](https://example.com) `y'), ('client', 'Claude Code ‮edoC'),
                           ('submitter', 'name\nline two'), ('model_label', 'tab\there')):
            self.assert_refused(self.declaration(**{key: value}))
        self.assertIn('\n', validator.check_declaration(self.declaration(notes='line one\nline two'))['notes'])
        self.assert_refused(self.declaration(notes='hidden ‮ text'))

    def test_every_bidirectional_and_invisible_character_is_refused(self):
        # verification of F13: U+061C ARABIC LETTER MARK (the last Bidi_Control character the
        # old list missed) and invisible format and separator characters passed.
        hidden = ('\u061c', '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff', '\u2028', '\u2029', '\u00ad',
                  '\u200e', '\u202a', '\u2066', '\U000e0041', '\ue000', '\x85')
        for char in hidden:
            for key in ('model_label', 'client', 'submitter'):
                with self.subTest(char=hex(ord(char)), key=key):
                    self.assert_refused(self.declaration(**{key: 'a' + char + 'b'}))
            with self.subTest(char=hex(ord(char)), key='notes'):
                self.assert_refused(self.declaration(notes='a' + char + 'b'))
        with self.assertRaises(validator.Fail) as caught:
            validator.check_declaration(self.declaration(client='a\u061cb'))
        self.assertIn('U+061C', str(caught.exception))
        plain = self.declaration(model_label='Modèle X — 2.1 (ß, 東京)', client='Claude Code 2.1, --tools ""',
                                 submitter='Zoë O\'Brien', notes='tabs\tand\r\nline breaks are fine here')
        self.assertEqual(validator.check_declaration(plain)['submitter'], 'Zoë O\'Brien')

    def scan(self, name, raw):
        files = {'SUBMISSION.json': self.declaration(), 'report.json': b'{}', name: raw}
        try:
            validator.check_secrets(files)
        except validator.Fail as failure:
            self.assertEqual(failure.check, 'secrets')
            return str(failure)
        return None

    def test_escaped_values_in_json_are_scanned(self):
        # \u002f is "/" and \u002d is "-": the raw bytes hold neither a path nor a key prefix.
        escaped = b'{"submitter": "alice (\\u002fhome\\u002falice)"}'
        self.assertIn('SUBMISSION.json (decoded)', self.scan('SUBMISSION.json', escaped))
        key = b'{"notes": "key sk\\u002dant\\u002dapi03\\u002d' + b'A' * 30 + b'"}'
        self.assertIn('SUBMISSION.json (decoded)', self.scan('SUBMISSION.json', key))

    def test_more_key_and_path_formats_are_caught(self):
        caught = ['api_key=' + 'Q7xYv2' * 3, 'token: ' + 'Q7xYv2' * 3, 'AccountKey=' + 'Q7xYv2' * 3,
                  'eyJ' + 'a' * 12 + '.' + 'b' * 12 + '.c', 'xai-' + 'a1' * 12, 'gsk_' + 'a1' * 12, 'npm_' + 'a1' * 12,
                  'r8_' + 'a1' * 12, 'sk_live_' + 'a1' * 12, 'rk_test_' + 'a1' * 12, '\\\\wsl.localhost\\Ubuntu',
                  '/' + 'home/émile/x', '/media/alice', '/run/user/1000/x', '/users/alice', '"/u/alice"']
        for text in caught:
            self.assertIsNotNone(self.scan('RESULT.md', text.encode()), text)

    def test_ordinary_text_passes_the_scan(self):
        for text in ('https://api.github.com/users/octocat', 'https://example.com/u/name', 'tokens: 1200 in, 300 out',
                     'the prompt in env/README.md, verbatim', 'Claude Code 2.1.300, --tools ""'):
            self.assertIsNone(self.scan('RESULT.md', text.encode()), text)

    def test_the_published_records_pass_the_scan(self):
        for folder in sorted((REPO / 'runs' / 'family').iterdir()) + [REPO / 'runs' / 'reference' / 'V1-amended']:
            files = {name: (folder / name).read_bytes() for name in ('run.json', 'actions.jsonl', 'report.json')}
            files['SUBMISSION.json'] = self.declaration()
            validator.check_secrets(files)

    def test_over_budget_and_empty_records_get_a_plain_message(self):
        with self.assertRaises(validator.Fail) as caught:
            validator.check_attempt_count([{}] * 1025)
        self.assertIn('cannot be scored or submitted', str(caught.exception))
        with self.assertRaises(validator.Fail) as caught:
            validator.check_attempt_count([])
        self.assertIn('no tool calls', str(caught.exception))
        validator.check_attempt_count([{}] * 1024)


class ValidateSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.short = root / 'short' / '2026-10-14-scripted-short-v1'
        serve(cls.short, [('look', {}), ('parts_bin', {}), ('inspect', {'target': 'no-such-part'})])
        submission(cls.short)
        cls.finish_only = root / 'finish' / '2026-10-14-scripted-finish-only-v1'
        serve(cls.finish_only, [('parts_bin', {}), ('finish', {})])
        submission(cls.finish_only)
        published = [json.loads(line) for line in (PUBLISHED / 'actions.jsonl').read_bytes().splitlines()]
        last_timing = max(i for i, row in enumerate(published) if row['name'] == 'check_timing')
        calls = [[row['name'], row['input']] for i, row in enumerate(published) if i != last_timing]
        (root / 'calls.json').write_text(json.dumps(calls))
        cls.no_final_timing = root / 'timing' / '2026-10-14-scripted-no-final-timing-check-v1'
        helper('make', str(cls.no_final_timing), str(root / 'calls.json'))
        submission(cls.no_final_timing)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self, label, source=None):
        source = source or self.short
        target = Path(self.tmp.name) / label / source.name
        shutil.copytree(source, target)
        return target

    def assert_passes(self, folder, summary):
        code, lines = run(folder)
        self.assertEqual(code, 0, lines)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f'PASS {folder}: {summary}'), lines)

    def assert_fails(self, folder, check, text=''):
        code, lines = run(folder)
        self.assertEqual(code, 1, lines)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f'FAIL {folder}: {check}:'), lines)
        self.assertIn(text, lines[0])

    def result_rows(self, folder):
        return validator.parse_result((folder / 'RESULT.md').read_bytes())

    def test_a_fresh_unfinished_run_passes(self):
        self.assert_passes(self.short, 'V1 0/18 S_partial 0.000000; files, declaration, secrets, chain, duplicate')
        code, lines = run(self.short)
        self.assertNotIn('REVIEW', lines[0])

    def test_a_finished_run_without_the_final_timing_check_passes(self):
        # redteam F1: the independent scorer's extra mistake type used to refuse this run.
        record = json.loads((self.no_final_timing / 'run.json').read_bytes())
        self.assertTrue(record['finished'])
        failed = [row['id'] for row in record['score']['primary_score']['checkpoints'] if not row['passed']]
        self.assertEqual(failed, ['CP11'])
        self.assert_passes(self.no_final_timing, 'V1 16/18 S_partial 0.444444')

    def test_a_near_copy_of_a_scripted_record_is_marked_for_review(self):
        # verification of F3: the published V1-correct calls without one call scored 16/18
        # and passed with nothing to tell the maintainer that it is a scripted run.
        code, lines = run(self.no_final_timing)
        self.assertEqual(code, 0, lines)
        self.assertIn('REVIEW BY HAND: 435 of its 435 calls are, in order, calls of runs/family/V1-correct', lines[0])
        self.assertEqual(self.result_rows(self.no_final_timing)['calls in common with a scripted record'],
                         '435 of 435, in order (runs/family/V1-correct, 436 calls)')

    def test_a_near_copy_of_another_submission_is_marked_for_review(self):
        root = Path(self.tmp.name) / 'near-submission'
        queries = [['search_service_info', {'query': f'head bolt torque step {i}'}] for i in range(24)]
        (root / 'first.json').parent.mkdir(parents=True)
        (root / 'first.json').write_text(json.dumps(queries))
        (root / 'second.json').write_text(json.dumps(queries + [['parts_bin', {}]]))
        first, second = root / '2026-10-14-model-a-v1', root / '2026-10-14-model-b-v1'
        for folder, calls in ((first, 'first.json'), (second, 'second.json')):
            helper('make', str(folder), str(root / calls))
            submission(folder)
        code, lines = run(first)
        self.assertEqual(code, 0, lines)
        self.assertIn('REVIEW BY HAND: 24 of its 24 calls are, in order, calls of runs/submitted/2026-10-14-model-b-v1',
                      lines[0])
        code, lines = run(second)
        self.assertEqual(code, 0, lines)
        self.assertIn('REVIEW BY HAND: 24 of its 25 calls are, in order, calls of runs/submitted/2026-10-14-model-a-v1',
                      lines[0])

    def test_result_md_shows_the_record_s_seconds_and_mistakes_like_the_board(self):
        # verification of F1 (caveat 1): RESULT.md showed the independent scorer's unknown
        # penalty (None) and its extra mistake event, while run.json and the board said otherwise.
        sys.path.insert(0, str(REPO / 'tools'))
        import build_board
        for folder in (self.finish_only, self.no_final_timing, self.short):
            record = json.loads((folder / 'run.json').read_bytes())
            rows = self.result_rows(folder)
            human = record['score']['human_time']
            self.assertEqual(rows['penalty seconds'], str(human['penalty_seconds']), folder.name)
            self.assertEqual(rows['productive seconds'], str(human['productive_seconds']), folder.name)
            self.assertEqual(rows['mistake events'], str(record['score']['mistakes']['count']), folder.name)
            self.assertNotIn('None', rows['penalty seconds'])
            board_row = build_board.row('x', 'm', 'c', 'V1', *build_board.from_score(record['score']), 'd', 's', False)
            self.assertEqual(rows['penalty seconds'], str(board_row['penalty_s']))
            self.assertEqual(rows['productive seconds'], str(board_row['productive_s']))
        self.assertEqual(self.result_rows(self.no_final_timing)['mistake events'], '0')

    def test_a_run_that_calls_finish_early_passes(self):
        self.assert_passes(self.finish_only, 'V1 0/18 S_partial 0.000000')

    def test_the_report_of_a_server_stopped_mid_run_is_accepted(self):
        # A client that kills the server leaves the report written after the last call.
        folder = self.copy('running')
        reports = json.loads(helper('reports', str(folder / 'run.json')))
        (folder / 'report.json').write_bytes(canonical(reports['running']))
        self.assert_passes(folder, 'V1 0/18')

    def test_report_rules_match_the_pinned_environment(self):
        for source in (self.short, self.finish_only):
            record = json.loads((source / 'run.json').read_bytes())
            for reason, report in json.loads(helper('reports', str(source / 'run.json'))).items():
                expected = validator.expected_report(record, 2.25, report['status'], report['terminal_reason'])
                self.assertEqual(canonical(expected), canonical(report), reason)
                self.assertIn((report['status'], report['terminal_reason']), validator.report_reasons(record))

    def test_an_exact_copy_of_a_published_record_is_refused(self):
        folder = Path(self.tmp.name) / 'copy' / '2026-10-14-copied-v1'
        folder.mkdir(parents=True)
        for name in ('run.json', 'actions.jsonl', 'report.json'):
            shutil.copyfile(PUBLISHED / name, folder / name)
        shutil.copyfile(self.short / 'SUBMISSION.json', folder / 'SUBMISSION.json')
        (folder / 'RESULT.md').write_text('placeholder\n')
        self.assert_fails(folder, 'duplicate', 'runs/family/V1-correct')

    def test_the_same_run_under_a_second_name_is_refused(self):
        first = self.copy('twice')
        second = first.parent / '2026-10-15-the-same-run-v1'
        shutil.copytree(first, second)
        self.assert_fails(second, 'duplicate', 'runs/submitted/' + first.name)

    def test_chain_break(self):
        folder = self.copy('chain')
        record = json.loads((folder / 'run.json').read_bytes())
        record['actions'][1]['previous_action_sha256'] = '0' * 64
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
        self.assertIn('| points | 0/18 |', text)
        (folder / 'RESULT.md').write_text(text.replace('| points | 0/18 |', '| points | 1/18 |'))
        self.assert_fails(folder, 'scorer', 'points')

    def test_result_md_must_be_exactly_the_generated_file(self):
        # redteam F5: a forged table shown first, the true rows hidden in a comment.
        folder = self.copy('forged-result')
        text = (folder / 'RESULT.md').read_text()
        forged = text.replace('| points | 0/18 |', '| points | 18/18 |').replace('| S_full | 0 |', '| S_full | 1 |')
        (folder / 'RESULT.md').write_text(forged + '<!--\n' + text + '-->\n')
        self.assert_fails(folder, 'scorer', 'not exactly the file')

    def test_report_json_must_be_the_environment_s_report(self):
        # redteam F6: every field but the wall-clock seconds follows from the record.
        changes = [lambda r: r['primary_score'].update(points_earned=18),
                   lambda r: r['tokens'].update(input=12, output=3, total=15, status='recorded'),
                   lambda r: r.update(endorsement='Verified by ToolsEnabled'),
                   lambda r: r.update(terminal_reason='finished', status='finished'),
                   lambda r: r['tool_calls'].update(refused=0, successful=3)]
        for index, change in enumerate(changes):
            folder = self.copy(f'report-{index}')
            report = json.loads((folder / 'report.json').read_bytes())
            change(report)
            (folder / 'report.json').write_bytes(canonical(report))
            self.assert_fails(folder, 'chain', 'report.json')
        folder = self.copy('report-indent')
        report = json.loads((folder / 'report.json').read_bytes())
        (folder / 'report.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n')
        self.assert_fails(folder, 'chain', 'report.json')

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

    def test_escaped_personal_path(self):
        # redteam F12: the JSON escape hid the path from the byte scan.
        folder = self.copy('escaped')
        raw = json.dumps({**DECLARATION, 'submitter': 'someone (' + '/' + 'home/someone)'}, indent=2)
        (folder / 'SUBMISSION.json').write_text(raw.replace('/', '\\u002f') + '\n')
        self.assert_fails(folder, 'secrets', 'decoded')

    def test_bad_date(self):
        folder = self.copy('date')
        (folder / 'SUBMISSION.json').write_text(json.dumps({**DECLARATION, 'date': '2026-10-14\n'}) + '\n')
        self.assert_fails(folder, 'declaration', 'date')

    def test_size_and_extra_files(self):
        folder = self.copy('extra')
        (folder / 'notes.txt').write_text('extra')
        self.assert_fails(folder, 'files')

    def test_size_message_names_the_look_calls(self):
        with mock.patch.object(validator, 'MAX_SUBMISSION_BYTES', 1000):
            with self.assertRaises(validator.Fail) as caught:
                validator.check_files(self.short)
        self.assertIn('look call', str(caught.exception))

    def test_write_result_does_not_follow_a_link(self):
        # redteam F11
        folder = self.copy('link')
        victim = folder.parent / 'victim.txt'
        victim.write_text('untouched\n')
        (folder / 'RESULT.md').unlink()
        (folder / 'RESULT.md').symlink_to(victim)
        with self.assertRaises(validator.Fail) as caught:
            validator.write_result(folder)
        self.assertEqual(caught.exception.check, 'files')
        self.assertEqual(victim.read_text(), 'untouched\n')


if __name__ == '__main__':
    unittest.main()
