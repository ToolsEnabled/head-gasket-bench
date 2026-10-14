"""Value behavior of the independent scorer; no producer imports or execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from job_accuracy.independent import assess, fingerprint, encoded
from job_accuracy.report import run_report, summary

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT/'evidence/job-accuracy/seven-inputs1'
HISTORY = ROOT/'evidence/job-accuracy/history-probe1'


def source(name='correct'):
    return json.loads((INPUTS/(name+'.json')).read_bytes())


def evaluate(record):
    settings = record['config']['repair_scoring']
    return assess(record,settings['reference'],settings['human_time_policy'])


def recommit(record):
    record['final_state']['identity']['action_history_sha256'] = fingerprint(record['final_state']['action_history'])
    record['final_state_sha256'] = fingerprint(record['final_state'])
    if record['actions']:
        record['actions'][-1]['post_state_sha256'] = record['final_state_sha256']


class IndependentAccuracy(unittest.TestCase):
    def test_correct_reference_and_replacement_are_full_credit(self):
        report = evaluate(source())
        self.assertEqual(report['bolt_accuracy']['final_accuracy_percent'],100)
        self.assertEqual(report['checklist_accuracy']['final_accuracy_percent'],100)
        self.assertEqual(report['human_time']['total_seconds'],5860)
        self.assertEqual(report['mistakes']['count'],0)
        replacement = next(row for row in report['bolt_accuracy']['bolts'] if row['sequence_index']==3)
        self.assertEqual(replacement['body_id'],'new_hb03')
        self.assertTrue(all(replacement['checks'].values()))

    def test_six_bad_value_histories_have_specific_mistakes_and_losses(self):
        kinds = {'wrong_torque_sequence':'wrong_order','under_torque':'wrong_torque_value',
                 'skipped_final_stage':'missing_torque_stage','wrong_gasket':'wrong_gasket',
                 'reused_stretched_bolt':'reused_stretched_bolt','wrong_timing':'timing_marks_off'}
        for name, kind in kinds.items():
            with self.subTest(name=name):
                report=evaluate(source(name))
                self.assertLess(report['checklist_accuracy']['final_accuracy_percent'],100)
                self.assertGreater(report['mistakes']['by_type'].get(kind,0),0)
                self.assertGreater(report['human_time']['penalty_seconds'],0)

    def test_replays_are_exact_without_execution_measurements(self):
        for name in ('correct','wrong_timing','under_torque'):
            self.assertEqual(encoded(evaluate(source(name))),encoded(evaluate(source(name))))

    def test_stale_installation_stage_cannot_get_current_credit(self):
        for name in ('partial_loosen_final_only','reinstalled_final_only'):
            record=json.loads((HISTORY/name/'replay-0.json').read_bytes())['run']
            report=evaluate(record)
            bolt=next(row for row in report['bolt_accuracy']['bolts'] if row['body_id']=='hb02')
            self.assertFalse(bolt['checks']['first_stage_value'])
            self.assertFalse(bolt['checks']['stage_order'])
            self.assertGreater(report['mistakes']['by_type']['missing_torque_stage'],0)

    def test_stale_timing_is_wrong_and_unpriced_rule_is_unknown(self):
        for name in ('timing_checked_before_repair','timing_reinstalled_after_check'):
            record=json.loads((HISTORY/name/'replay-0.json').read_bytes())['run']
            report=evaluate(record)
            item=next(r for r in report['checklist_accuracy']['items'] if r['item']=='timing/check_completed')
            self.assertFalse(item['correct'])
            self.assertEqual(report['mistakes']['by_type']['missing_timing_verification'],1)
            self.assertIsNone(report['human_time']['total_seconds'])
            self.assertTrue(report['human_time']['unpriced_mistakes'])

    def test_unknown_bolt_measurement_is_not_zero_or_failure(self):
        record=source();record['final_state']['bolts']['hb01']['stretch_mm']=None;recommit(record)
        report=evaluate(record)
        bolt=next(row for row in report['bolt_accuracy']['bolts'] if row['body_id']=='hb01')
        self.assertIsNone(bolt['checks']['bolt_condition'])
        self.assertEqual(report['bolt_accuracy']['unknown'],1)
        self.assertIsNone(report['bolt_accuracy']['final_accuracy_percent'])

    def test_assembly_part_damage_is_scored_explicitly(self):
        record=source();record['final_state']['parts']['head']['damaged']=True;recommit(record)
        report=evaluate(record)
        damage=next(r for r in report['checklist_accuracy']['items'] if r['item']=='part/head/undamaged')
        self.assertFalse(damage['correct'])
        self.assertLess(report['checklist_accuracy']['final_accuracy_percent'],100)
        self.assertIn('part/head/undamaged',report['producer_comparison']['independent_only_items'])

    def test_producer_score_does_not_determine_independent_accuracy(self):
        record=source();first=evaluate(record)
        for value in (None,2,{'schema':'hgj/repair-score/v1'}, {'schema':'other'}):
            record['score']=value
            second=evaluate(record)
            for field in ('bolt_accuracy','checklist_accuracy','mistakes','human_time'):
                self.assertEqual(first[field],second[field])

    def test_empty_prefix_has_observed_metrics_but_no_final_accuracy(self):
        base=json.loads((HISTORY/'correct_reference/replay-0.json').read_bytes())
        record=base['run'];record.update(actions=[],final_state=base['initial'],score=None,finished=False,scoring_status='unavailable')
        recommit(record)
        report=evaluate(record)
        self.assertEqual(report['status'],'partial')
        self.assertIsNone(report['bolt_accuracy']['final_accuracy_percent'])
        self.assertIsNotNone(report['bolt_accuracy']['observed_accuracy_percent'])
        self.assertEqual(report['tool_calls'],{'attempted':0,'successful':0,'refused':0})
        self.assertEqual(report['human_time']['total_seconds'],0)

    def test_report_preserves_unknown_usage_and_partial_active_attempt(self):
        report=run_report(evaluate(source()),active_attempt={'status':'uncommitted_unknown','reason':'Last dispatch was interrupted'})
        self.assertIsNone(report['agent_wall_time']['seconds'])
        self.assertIsNone(report['tokens']['total'])
        self.assertEqual(report['committed_tool_calls']['attempted'],187)
        self.assertIn('Unknown',summary(report))
        self.assertIn('Last dispatch was interrupted',summary(report))

    def test_report_known_usage_keeps_counts_separate(self):
        report=run_report(evaluate(source()),wall_seconds=1.5,wall_source='Authored timing value test',
                          tokens={'input':20,'output':7},token_source='Authored token value test')
        self.assertEqual(report['tokens']['total'],27)
        self.assertEqual(report['agent_wall_time']['seconds'],1.5)
        self.assertEqual(report['assessment']['human_time']['total_seconds'],5860)


if __name__ == '__main__':
    unittest.main()
