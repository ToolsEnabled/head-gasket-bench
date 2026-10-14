"""Behavioral checks for measured usage separate from deterministic replay."""
import copy
import unittest
from hgj.codec import digest
from hgj.repair_report import report_for_run


def record():
    score = {
        'schema': 'hgj/repair-score/v1', 'status': 'scored', 'tool_calls': 2,
        'human_time': {'productive_seconds': 12, 'penalty_seconds': 30, 'total_seconds': 42},
        'mistakes': {'count': 1, 'by_type': {'blocked_removal': 1}, 'events': []},
        'bolt_accuracy': {'accuracy_percent': 100},
        'checklist_accuracy': {'accuracy_percent': 90},
        'coverage': {'dowels': 'not modeled in supplied geometry'},
        'reference_sha256': 'a'*64,
    }
    return {'score': score, 'score_sha256': digest(score), 'finished': True,
            'actions': [{'name':'remove', 'result': {'ok': False}}, {'name':'finish', 'result': {'ok': True}}]}


class ReportTests(unittest.TestCase):
    def test_usage_and_charge_are_separate(self):
        source = record()
        before = copy.deepcopy(source)
        result = report_for_run(source, 1.25, tokens={'input': 17, 'output': 5},
                                token_source='Authored test usage receipt')
        self.assertEqual(result['real_time']['seconds'], 1.25)
        self.assertEqual(result['tokens']['total'], 22)
        self.assertEqual(result['human_time']['total_seconds'], 42)
        self.assertEqual(result['tool_calls'], {'attempted': 2, 'successful': 1, 'refused': 1})
        self.assertEqual(result['run_sha256'], digest(source))
        self.assertEqual(source, before)
        result['human_time']['total_seconds'] = 9
        self.assertEqual(source, before)

    def test_unknown_tokens_are_not_zero(self):
        result = report_for_run(record(), 0)
        self.assertEqual(result['tokens']['status'], 'not_recorded')
        self.assertIsNone(result['tokens']['total'])
        self.assertEqual(result['coverage']['dowels'], 'not modeled in supplied geometry')

    def test_invalid_clock_rejected(self):
        for value in (-1, float('inf'), float('nan'), True, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                report_for_run(record(), value)

    def test_missing_usage_sources_rejected(self):
        with self.assertRaises(ValueError):
            report_for_run(record(), 1, time_source='')
        with self.assertRaises(ValueError):
            report_for_run(record(), 1, token_source='')

    def test_invalid_token_values_rejected(self):
        for value in ({'input': True, 'output': 2}, {'input': -1, 'output': 0},
                      {'input': 1.0, 'output': 2}, {'input': 0}, {'input': 1, 'output': 2, 'total': 3}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                report_for_run(record(), 1, tokens=value)

    def test_changed_score_rejected(self):
        source = record()
        source['score']['human_time']['total_seconds'] = 0
        with self.assertRaises(ValueError):
            report_for_run(source, 1)

    def test_nonprocedure_score_rejected(self):
        source = record()
        source['score']['schema'] = 'unrelated/result'
        source['score_sha256'] = digest(source['score'])
        with self.assertRaises(ValueError):
            report_for_run(source, 1)

    def test_inconsistent_finished_flag_rejected(self):
        source = record()
        source['finished'] = False
        with self.assertRaises(ValueError):
            report_for_run(source, 1)

    def test_unscored_result_rejected(self):
        source = record()
        source['score']['status'] = 'in_progress'
        source['score_sha256'] = digest(source['score'])
        with self.assertRaises(ValueError):
            report_for_run(source, 1)

    def test_partial_report_retains_latest_score_and_reason(self):
        source = record()
        source['finished'] = False
        source['actions'][-1]['name'] = 'look'
        source['score']['status'] = 'in_progress'
        source['score_sha256'] = digest(source['score'])
        for reason in ('budget_exhausted', 'interrupted', 'input_ended_without_finish'):
            result = report_for_run(source, 1, terminal_reason=reason)
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual(result['terminal_reason'], reason)
            self.assertEqual(result['score_sha256'], source['score_sha256'])
            self.assertEqual(result['tool_calls']['attempted'],
                             result['tool_calls']['successful'] + result['tool_calls']['refused'])

    def test_malformed_action_outcomes_rejected(self):
        for outcome in (1, 0, None, 'yes'):
            source = record()
            source['actions'][0]['result']['ok'] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                report_for_run(source, 1)

    def test_finished_without_successful_finish_rejected(self):
        source = record()
        source['actions'][-1]['name'] = 'look'
        with self.assertRaises(ValueError):
            report_for_run(source, 1)

    def test_invalid_terminal_reason_rejected(self):
        with self.assertRaises(ValueError):
            report_for_run(record(), 1, terminal_reason='interrupted')

    def test_tool_call_count_rejected(self):
        source = record()
        source['actions'].pop()
        with self.assertRaises(ValueError):
            report_for_run(source, 1)


if __name__ == '__main__':
    unittest.main()
