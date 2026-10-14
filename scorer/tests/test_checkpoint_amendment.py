"""Amended-rule values; no historical job is regraded by these examples."""
from copy import deepcopy
import unittest
from job_accuracy.checkpoints import same_loosening
from job_accuracy.checkpoint_contracts import documented_loosening,selected_revision,ORIGINAL,AMENDMENT1
from job_accuracy.independent import AssessmentInputError


def values():
    fasteners={f'position-{i}':{'group':'head','sequence_index':i} for i in range(1,11)}
    rows=[{'part_id':f'position-{i}','mode':'loosen','angle_deg':-120} for _ in range(3) for i in range(10,0,-1)]
    return rows,deepcopy(rows),fasteners


class CheckpointAmendment(unittest.TestCase):
    def test_rule_version_is_explicit_and_typed(self):
        for value in (ORIGINAL,AMENDMENT1):self.assertEqual(selected_revision(value),value)
        for value in (None,True,1,{},'latest','unknown'):
            with self.assertRaisesRegex(AssessmentInputError,'checkpoint-rule-version'):selected_revision(value)

    def test_both_documented_whole_sequences_pass(self):
        actual,expected,fasteners=values()
        self.assertTrue(documented_loosening(actual,expected,fasteners,same_loosening))
        for start in range(0,30,10):
            actual[start:start+10]=[actual[start+i] for i in (0,1,2,3,4,7,6,5,8,9)]
        self.assertTrue(documented_loosening(actual,expected,fasteners,same_loosening))
        self.assertFalse(same_loosening(actual,expected))

    def test_missing_pass_wrong_angle_or_unlisted_order_fails(self):
        a,e,f=values()
        for mutate in (lambda r:r.pop(),lambda r:r[0].update(angle_deg=-60),
                       lambda r:r[0].update(angle_deg=True),lambda r:r[0].update(mode='tighten'),
                       lambda r:r.__setitem__(slice(0,2),[r[1],r[0]])):
            changed=deepcopy(a);mutate(changed)
            self.assertFalse(documented_loosening(changed,e,f,same_loosening))

    def test_equal_numeric_values_and_renamed_bodies_preserve_result(self):
        a,e,f=values()
        for rows in (a,e):
            for row in rows:row['part_id']='renamed-'+row['part_id']
        f={'renamed-'+pid:value for pid,value in f.items()}
        for row in a:row['angle_deg']=-120.0
        self.assertTrue(documented_loosening(a,e,f,same_loosening))

    def test_incomplete_or_boolean_position_definition_is_named_refusal(self):
        for mutate in (lambda f:f.pop('position-1'),lambda f:f['position-1'].update(sequence_index=True),
                       lambda f:f['position-1'].update(sequence_index=2)):
            a,e,f=values();mutate(f)
            with self.assertRaisesRegex(AssessmentInputError,'loosening-service-positions'):
                documented_loosening(a,e,f,same_loosening)

    def test_reference_must_describe_complete_numerical_passes(self):
        a,e,f=values()
        for mutate in (lambda r:r.pop(),lambda r:r[0].update(angle_deg=None),
                       lambda r:r[0].update(part_id=r[1]['part_id'])):
            reference=deepcopy(e);mutate(reference)
            self.assertFalse(documented_loosening(a,reference,f,same_loosening))
