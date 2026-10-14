"""Compact finish value/stdio checks; no Game, backend, trajectory or replay."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hgj import mcp
from hgj.codec import canonical, digest
from hgj.repair_report import report_for_run
from tools.repair_demo import verify_case

# Sandbox evidence folder replaced by the ordinary temporary directory.


def supplied_record(padding=0):
    score = {
        'schema': 'hgj/repair-score/v1', 'status': 'scored', 'tool_calls': 1,
        'reference_sha256': 'a' * 64,
        'human_time': {'productive_seconds': 12, 'penalty_seconds': 0,
                       'total_seconds': 12, 'reference_seconds': 12, 'ledger': []},
        'mistakes': {'count': 0, 'by_type': {}, 'events': []},
        'bolt_accuracy': {'correct': 60, 'total': 60, 'accuracy_percent': 100,
                          'bolts': [{'authored_full_details': 'retained'}]},
        'checklist_accuracy': {'correct': 1647, 'total': 1647, 'accuracy_percent': 100,
                               'items': [{'authored_full_details': 'retained'}]},
        'primary_score': {'schema': 'hgj/repair-checkpoints/v1', 'points_earned': 18,
                          'total_points': 18, 'S_full': 1, 'S_partial': 1.0,
                          'checkpoints': [{'authored_full_details': 'retained'}]},
        'coverage': {'scope': 'Authored transport value; no checkpoint reduction'},
        'authored_padding': ('"\\\n\u03bb' * padding),
    }
    final = {'authored_state': 'retained'}
    result = {'ok': True, 'scoring_status': 'scored', 'score': copy.deepcopy(score),
              'turns_remaining': 7}
    return {
        'schema': 'hgj/run/v1', 'config': {'factors': {'tool_call_limit': 1024}},
        'actions': [{'seq': 1, 'name': 'finish', 'input': {}, 'result': result}],
        'final_state': final, 'final_state_sha256': digest(final),
        'score': score, 'score_sha256': digest(score),
        'finished': True, 'scoring_status': 'scored',
    }


def sync_score(record):
    record['score_sha256'] = digest(record['score'])
    record['actions'][-1]['result']['score'] = copy.deepcopy(record['score'])


class SuppliedGame:
    """Transport stub returns supplied snapshots; never invokes Game or scoring."""
    procedure_scoring = True

    def __init__(self, completed=None, refusal=False):
        self.completed = copy.deepcopy(completed or supplied_record())
        self.current = copy.deepcopy(self.completed)
        self.current['actions'] = []
        self.current['finished'] = False
        self.current['scoring_status'] = 'in_progress'
        self.current['score']['status'] = 'in_progress'
        self.current['score']['tool_calls'] = 0
        self.current['score_sha256'] = digest(self.current['score'])
        self.records = self.current['actions']
        self.refusal = refusal
        self.calls = []

    def export(self):
        return copy.deepcopy(self.current)

    def tools(self):
        return [{'name': 'finish', 'inputSchema': {'type': 'object'}}]

    def call(self, name, args):
        self.calls.append((name, copy.deepcopy(args)))
        if self.refusal:
            value = {'ok': False, 'refusal': 'Authored transport refusal'}
            self.current['actions'] = [{'seq': 1, 'name': name, 'input': args,
                                        'result': copy.deepcopy(value)}]
            self.current['score']['tool_calls'] = 1
            self.current['score_sha256'] = digest(self.current['score'])
        else:
            self.current = copy.deepcopy(self.completed)
            value = copy.deepcopy(self.current['actions'][-1]['result'])
        self.records = self.current['actions']
        return value


def requests(identifier=7, name='finish', list_tools=False):
    rows = [
        {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
         'params': {'protocolVersion': '2025-11-25'}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
    ]
    if list_tools:
        rows.append({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}})
    rows.append({'jsonrpc': '2.0', 'id': identifier, 'method': 'tools/call',
                 'params': {'name': name, 'arguments': {}}})
    return rows


def transport(game, directory, identifier=7, name='finish', sink=None):
    rows = requests(identifier, name)
    stream = io.StringIO(b''.join(canonical(row) for row in rows).decode())
    sink = sink or io.StringIO()
    outcome = mcp.serve(game, stream, sink, directory)
    return outcome, sink


class CompactFinishTests(unittest.TestCase):
    def temp(self):
        directory = tempfile.TemporaryDirectory(prefix='unit-')
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_summary_scalars_and_full_record_pin(self):
        record = supplied_record(1000)
        before = copy.deepcopy(record)
        value = mcp.finish_summary(record)
        self.assertIs(value['ok'], True)
        self.assertEqual(value['schema'], 'hgj/finish-summary/v1')
        self.assertEqual(value['record'], {'file': 'finish-record.json',
            'sha256': digest(record), 'bytes': len(canonical(record))})
        self.assertEqual(value['score_summary']['primary_score']['points_earned'], 18)
        self.assertEqual(value['score_summary']['bolt_accuracy'],
                         {'correct': 60, 'total': 60, 'accuracy_percent': 100})
        self.assertEqual(value['score_summary']['checklist_accuracy'],
                         {'correct': 1647, 'total': 1647, 'accuracy_percent': 100})
        self.assertEqual(value['score_summary']['human_time']['total_seconds'], 12)
        self.assertEqual(value['score_summary']['mistakes'], {'count': 0, 'by_type': {}})
        self.assertEqual(value['score_summary']['tool_calls'], 1)
        self.assertEqual(value['turns_remaining'], 7)
        self.assertNotIn('authored_padding', value['score_summary'])
        self.assertNotIn('score', value)
        value['score_summary']['mistakes']['by_type']['authored'] = 9
        self.assertEqual(record, before)

    def test_summary_preserves_loss_values(self):
        record = supplied_record()
        record['score']['primary_score'].update(points_earned=14, S_full=0, S_partial=7/18)
        record['score']['bolt_accuracy'].update(correct=40, accuracy_percent=100*40/60)
        record['score']['checklist_accuracy'].update(correct=1640, accuracy_percent=100*1640/1647)
        record['score']['human_time'].update(productive_seconds=9, penalty_seconds=30, total_seconds=39)
        record['score']['mistakes'].update(count=2, by_type={'wrong_order': 2})
        sync_score(record)
        value = mcp.finish_summary(record)['score_summary']
        for key in ('primary_score', 'bolt_accuracy', 'checklist_accuracy', 'human_time', 'mistakes'):
            for field, actual in value[key].items():
                self.assertEqual(actual, record['score'][key][field])

    def test_real_serialized_finish_line_below_one_mib(self):
        record = supplied_record(200000)
        identifier = '"\\\n\u03bb' * 6000
        self.assertLess(len(canonical(requests(identifier)[-1])), 65536)
        directory = self.temp()
        outcome, sink = transport(SuppliedGame(record), directory, identifier)
        lines = sink.getvalue().splitlines(keepends=True)
        self.assertEqual(outcome, {'actions': 1, 'finished': True})
        self.assertLess(len(lines[-1].encode('utf-8')), 1024**2)
        reply = json.loads(lines[-1])
        self.assertEqual(reply['id'], identifier)
        self.assertIs(reply['result']['isError'], False)
        compact = json.loads(reply['result']['content'][0]['text'])
        self.assertEqual(compact, mcp.finish_summary(record))
        self.assertGreater(len(canonical(record['actions'][-1]['result'])), 1024**2)

    def test_full_disk_snapshot_journal_and_report_custody(self):
        record = supplied_record(1000)
        directory = self.temp()
        _, sink = transport(SuppliedGame(record), directory)
        snapshot = (directory/'finish-record.json').read_bytes()
        self.assertEqual(snapshot, canonical(record))
        self.assertEqual((directory/'run.json').read_bytes(), snapshot)
        self.assertEqual((directory/'actions.jsonl').read_bytes(),
                         b''.join(canonical(row) for row in record['actions']))
        report = json.loads((directory/'report.json').read_bytes())
        self.assertEqual(report['run_sha256'], digest(record))
        self.assertEqual(report['score_sha256'], record['score_sha256'])
        self.assertEqual(report['bolt_accuracy'], record['score']['bolt_accuracy'])
        self.assertEqual(report['checklist_accuracy'], record['score']['checklist_accuracy'])
        self.assertEqual(report['primary_score'], record['score']['primary_score'])
        self.assertEqual(report['human_time'], record['score']['human_time'])
        self.assertEqual(report['mistakes'], record['score']['mistakes'])
        self.assertEqual(report['terminal_reason'], 'finished')
        self.assertIsNone(report['tokens']['total'])
        compact = json.loads(json.loads(sink.getvalue().splitlines()[-1])['result']['content'][0]['text'])
        self.assertEqual(compact['record']['sha256'], digest(json.loads(snapshot)))
        self.assertEqual(compact['record']['bytes'], len(snapshot))

    def test_snapshot_exists_before_finish_reply(self):
        record = supplied_record()
        directory = self.temp()
        class CommitObservingSink(io.StringIO):
            def write(inner, text):
                reply = json.loads(text)
                if reply.get('id') == 7 and 'result' in reply:
                    self.assertTrue((directory/'finish-record.json').is_file())
                    self.assertTrue((directory/'report.json').is_file())
                    self.assertEqual((directory/'finish-record.json').read_bytes(), canonical(record))
                    self.assertEqual((directory/'run.json').read_bytes(), canonical(record))
                    self.assertEqual(json.loads((directory/'report.json').read_bytes())['run_sha256'], digest(record))
                return super().write(text)
        transport(SuppliedGame(record), directory, sink=CommitObservingSink())

    def test_existing_snapshot_refuses_start_without_dispatch_or_changes(self):
        directory = self.temp()
        sentinel = b'Prior immutable finish snapshot\n'
        (directory/'finish-record.json').write_bytes(sentinel)
        game = SuppliedGame()
        with self.assertRaisesRegex(FileExistsError, 'existing run output'):
            transport(game, directory)
        self.assertEqual(game.calls, [])
        self.assertEqual((directory/'finish-record.json').read_bytes(), sentinel)
        self.assertFalse((directory/'actions.jsonl').exists())

    def test_refused_finish_never_gets_success_summary_or_snapshot(self):
        directory = self.temp()
        _, sink = transport(SuppliedGame(refusal=True), directory)
        reply = json.loads(sink.getvalue().splitlines()[-1])
        self.assertIs(reply['result']['isError'], True)
        self.assertEqual(json.loads(reply['result']['content'][0]['text']),
                         {'ok': False, 'refusal': 'Authored transport refusal'})
        self.assertFalse((directory/'finish-record.json').exists())
        self.assertIs(json.loads((directory/'run.json').read_bytes())['finished'], False)

    def test_summary_rejects_uncommitted_finish(self):
        mutations = ('finished', 'last_name', 'last_ok', 'last_ok_false', 'score_pin', 'finish_score', 'schema')
        for mutation in mutations:
            record = supplied_record()
            if mutation == 'finished': record['finished'] = 1
            if mutation == 'last_name': record['actions'][-1]['name'] = 'look'
            if mutation == 'last_ok': record['actions'][-1]['result']['ok'] = 1
            if mutation == 'last_ok_false': record['actions'][-1]['result']['ok'] = False
            if mutation == 'score_pin': record['score_sha256'] = '0' * 64
            if mutation == 'finish_score': record['actions'][-1]['result']['score']['tool_calls'] = False
            if mutation == 'schema':
                record['score']['schema'] = 'unrelated-score/v1'
                sync_score(record)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'committed scored finish'):
                mcp.finish_summary(record)

    def test_summary_requires_consistent_status_and_call_census(self):
        for mutation in ('score_status', 'record_status', 'call_count', 'typed_call_count'):
            record = supplied_record()
            if mutation == 'score_status': record['score']['status'] = 'in_progress'
            if mutation == 'record_status': record['scoring_status'] = 'in_progress'
            if mutation == 'call_count': record['score']['tool_calls'] = 2
            if mutation == 'typed_call_count': record['score']['tool_calls'] = True
            sync_score(record)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                mcp.finish_summary(record)

    def test_summary_rejects_nonlist_actions_and_prior_typed_outcomes(self):
        record = supplied_record()
        record['actions'] = tuple(record['actions'])
        with self.assertRaisesRegex(ValueError, 'committed scored finish'):
            mcp.finish_summary(record)
        record = supplied_record()
        record['actions'].insert(0, {'seq': 0, 'name': 'look', 'input': {},
                                      'result': {'ok': 1}})
        record['score']['tool_calls'] = 2
        sync_score(record)
        with self.assertRaisesRegex(ValueError, 'committed scored finish'):
            mcp.finish_summary(record)

    def test_size_guard_refuses_large_summary_not_large_full_record(self):
        record = supplied_record(1000)
        self.assertLess(len(canonical(mcp.finish_summary(record))), 16384)
        record['score']['mistakes']['by_type'] = {'authored-too-large': 'x' * 20000}
        sync_score(record)
        with self.assertRaisesRegex(ValueError, 'transport limit'):
            mcp.finish_summary(record)

    def test_complete_wire_guard_counts_nested_escaping_and_request_id(self):
        directory = self.temp()
        identifier = '"\\\n\u03bb' * 6000
        record = supplied_record()
        compact = mcp.finish_summary(record)
        self.assertLess(len(canonical(compact)), 16384)
        incoming = canonical(requests(identifier)[-1])
        self.assertLess(len(incoming), 65536)
        wire = canonical({'jsonrpc': '2.0', 'id': identifier, 'result': {
            'isError': False, 'content': [{'type': 'text',
                'text': canonical(compact).decode().strip()}]}})
        # 1KiB is a declared reduced test cap; actual production cap remains1MiB.
        self.assertGreater(len(wire), 1024)
        with patch.object(mcp, 'MAX_FINISH_RESPONSE_BYTES', 1024):
            _, sink = transport(SuppliedGame(record), directory, identifier)
        reply = json.loads(sink.getvalue().splitlines()[-1])
        self.assertIn('error', reply)
        self.assertNotIn('result', reply)
        self.assertEqual(reply['id'], identifier)
        self.assertEqual((directory/'finish-record.json').read_bytes(), canonical(record))

    def test_summary_limit_refusal_retains_full_committed_disk_record(self):
        record = supplied_record()
        record['score']['mistakes'].update(count=1, by_type={'x' * 20000: 1})
        sync_score(record)
        directory = self.temp()
        _, sink = transport(SuppliedGame(record), directory)
        reply = json.loads(sink.getvalue().splitlines()[-1])
        self.assertIn('error', reply)
        self.assertNotIn('result', reply)
        self.assertEqual((directory/'run.json').read_bytes(), canonical(record))
        self.assertFalse((directory/'finish-record.json').exists())

    def test_snapshot_write_failure_never_publishes_compact_success(self):
        directory = self.temp()
        original = mcp.atomic
        def fail_snapshot(path, value):
            if Path(path).name == 'finish-record.json':
                raise OSError('Authored snapshot write failure')
            return original(path, value)
        sink = io.StringIO()
        with patch.object(mcp, 'atomic', fail_snapshot), self.assertRaisesRegex(OSError, 'snapshot write failure'):
            transport(SuppliedGame(), directory, sink=sink)
        self.assertEqual([r['id'] for r in map(json.loads, sink.getvalue().splitlines())], [0])
        self.assertFalse((directory/'finish-record.json').exists())
        self.assertIs(json.loads((directory/'run.json').read_bytes())['finished'], True)

    def test_run_write_interruption_keeps_prior_committed_snapshot(self):
        directory = self.temp()
        game = SuppliedGame()
        prior = game.export()
        original = mcp.atomic
        interrupted = False
        def interrupt_first_run(path, value):
            nonlocal interrupted
            if Path(path).name == 'run.json' and not interrupted:
                interrupted = True
                raise KeyboardInterrupt('Authored precommit interruption')
            return original(path, value)
        sink = io.StringIO()
        with patch.object(mcp, 'atomic', interrupt_first_run), self.assertRaises(KeyboardInterrupt):
            transport(game, directory, sink=sink)
        self.assertEqual((directory/'run.json').read_bytes(), canonical(prior))
        self.assertEqual((directory/'actions.jsonl').read_bytes(), b'')
        report = json.loads((directory/'report.json').read_bytes())
        self.assertEqual(report['terminal_reason'], 'interrupted')
        self.assertIs(report['finished'], False)
        self.assertFalse((directory/'finish-record.json').exists())
        self.assertEqual(len(sink.getvalue().splitlines()), 1)

    def test_harness_joins_compact_reply_to_full_finish_result(self):
        record = supplied_record()
        rows = requests(list_tools=True)
        reply_values = [{'tools': []}, mcp.finish_summary(record)]
        replies = [{'jsonrpc': '2.0', 'id': 0, 'result': {}}]
        replies.append({'jsonrpc': '2.0', 'id': 1, 'result': reply_values[0]})
        replies.append({'jsonrpc': '2.0', 'id': 7, 'result': {'isError': False,
            'content': [{'type': 'text', 'text': canonical(reply_values[1]).decode().strip()}]}})
        journal = b''.join(canonical(row) for row in record['actions'])
        # These two supplied canonical copies isolate harness value gates; no replay ran.
        replays = [canonical(record), canonical(record)]
        self.assertEqual(verify_case('correct', record['config'], rows, replies, record, journal, replays), record['score'])
        compact = json.loads(replies[-1]['result']['content'][0]['text'])
        compact['record']['sha256'] = '0' * 64
        replies[-1]['result']['content'][0]['text'] = canonical(compact).decode().strip()
        with self.assertRaisesRegex(ValueError, 'reply_values'):
            verify_case('correct', record['config'], rows, replies, record, journal, replays)


if __name__ == '__main__':
    unittest.main(verbosity=2)
