"""Unrestored attachment obligations are one finish mistake, not N tool calls."""
from copy import deepcopy
import unittest
import test_source_removal as removal_fixture
from test_checkpoint_chronology import rechain
from tools.test_repair_checkpoints import evaluate
from job_accuracy import independent as core


def incomplete(priced=True):
    r=removal_fixture.SourceCheckpointIntegration().joined()
    r['actions']=[a for a in r['actions'] if a['name']!='restore_attachment']
    state=r['final_state']['benchmark_removal'];state['released']['tie']=True
    state['attachment_history']=[a for a in state['attachment_history'] if a['action']!='restore_attachment']
    policy=r['config']['repair_scoring']['human_time_policy']
    if priced:
        row=deepcopy(next(iter(policy['mistakes'].values())));row['seconds']=77
        policy['mistakes']['missing_attachment_restore']=row
    return rechain(r)


class AttachmentCharge(unittest.TestCase):
    def test_missing_restore_fails_only_reassembly_and_charges_finish_once(self):
        r=incomplete();a=evaluate(r);cp={v['id']:v for v in a['primary_score']['checkpoints']}
        self.assertTrue(cp['CP02']['passed']);self.assertFalse(cp['CP12']['passed'])
        self.assertEqual(a['mistakes']['by_type'],{'missing_attachment_restore':1})
        detail=a['mistakes']['events'][0]['detail']['attachment_obligations']
        self.assertEqual(detail['outstanding_release_ids'],['tie']);self.assertEqual(detail['mismatches'],[])
        charge=a['human_time']['ledger'][-1]
        self.assertEqual(charge['penalty_seconds'],77)
        self.assertEqual(charge['productive_seconds'],r['config']['repair_scoring']['human_time_policy']['actions']['finish']['seconds'])
        self.assertEqual(a['tool_calls']['attempted'],len(r['actions']))

    def test_old_unpriced_policy_reports_unknown_penalty_not_zero(self):
        a=evaluate(incomplete(False))
        self.assertEqual(a['mistakes']['by_type'],{'missing_attachment_restore':1})
        self.assertIsNone(a['human_time']['penalty_seconds']);self.assertIsNone(a['human_time']['total_seconds'])

    def test_false_restored_flag_does_not_hide_history_obligation(self):
        r=incomplete();r['final_state']['benchmark_removal']['released']['tie']=False
        a=evaluate(rechain(r));self.assertEqual(a['mistakes']['by_type'],{'missing_attachment_restore':1})
        self.assertIn('released',a['mistakes']['events'][0]['detail']['attachment_obligations']['mismatches'])

    def test_complete_or_unfinished_prefix_has_no_finish_charge(self):
        a=evaluate(removal_fixture.SourceCheckpointIntegration().joined());self.assertNotIn('missing_attachment_restore',a['mistakes']['by_type'])
        r=incomplete();r['actions']=[a for a in r['actions'] if a['name']!='finish'];r['finished']=False
        a=evaluate(rechain(r));self.assertNotIn('missing_attachment_restore',a['mistakes']['by_type'])
        self.assertEqual(a['status'],'partial')

    def test_many_missing_attachments_are_not_many_attempts(self):
        source={'available':True,'final_released':{'a':True,'b':True,'unused':False},'state_mismatches':[]}
        self.assertEqual(core.attachment_obligations(source)['outstanding_release_ids'],['a','b'])
        source['final_released']={k:False for k in source['final_released']}
        self.assertFalse(core.attachment_obligations(source)['missing'])
        source['state_mismatches']=['attachment_history/count']
        self.assertTrue(core.attachment_obligations(source)['missing'])

if __name__=='__main__':unittest.main()
