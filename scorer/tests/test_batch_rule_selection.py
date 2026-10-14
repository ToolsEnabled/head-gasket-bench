"""Host rule forwarding on authored records, without running a delivery."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from job_accuracy import independent as core
from job_accuracy.checkpoint_contracts import ORIGINAL,AMENDMENT1
from tools import receive_current_variants as reader
from test_amendment_integration import benchmark,diagram,reuse,rechain,retime
from test_amendment_passes import record,REVERSE,DIAGRAM
from test_successor_components import event


class BatchRuleSelection(unittest.TestCase):
    def test_original_default_ignores_record_selected_rule(self):
        r=rechain(reuse(diagram(benchmark())))
        baseline=reader.assess_case(deepcopy(r))
        r['checkpoint_revision']=AMENDMENT1;r['config']['checkpoint_revision']=AMENDMENT1
        # The config commitment is restored; the authored revision fields have no authority.
        rechain(r)
        value=reader.assess_case(r)
        self.assertEqual(value['primary_score'],baseline['primary_score'])
        self.assertNotEqual(value['primary_score']['points_earned'],18)

    def test_explicit_amended_rules_reach_actual_assessment(self):
        r=reuse(record((REVERSE,DIAGRAM,REVERSE)))
        r['actions'].insert(0,event('inspect',{'target':'belt'},{'damaged':False}))
        r=retime(r)
        original=reader.assess_case(deepcopy(r),ORIGINAL)
        amended=reader.assess_case(deepcopy(r),AMENDMENT1)
        self.assertEqual(amended['checkpoint_revision'],AMENDMENT1)
        self.assertEqual(amended['primary_score']['points_earned'],18)
        self.assertEqual(amended['mistakes']['count'],0)
        self.assertEqual(original['primary_score']['points_earned'],15)

    def test_unknown_rule_refuses_before_receiving_io(self):
        for revision in (None,True,'latest'):
            with patch.object(reader,'check_resources',side_effect=AssertionError('unexpected receiving I/O')):
                with self.assertRaisesRegex(core.AssessmentInputError,'checkpoint-rule-version'):
                    reader.main(Path('unused'),'',Path('unused'),Path('unused'),checkpoint_revision=revision)

    def test_amended_report_discloses_host_selection(self):
        r=reader.summary({'cases':[],'checkpoint_revision':AMENDMENT1})
        self.assertIn('Host-selected rules: Amendment 1',r)
        self.assertNotIn('Host-selected rules: Amendment 1',reader.summary({'cases':[]}))
