"""Amendment 2 preserves one order across passes and keeps cover reuse."""
from copy import deepcopy
from itertools import product
import unittest
from job_accuracy import checkpoint_contracts as rules
from job_accuracy.checkpoints import same_loosening
from job_accuracy.report import run_report,summary
from tools import receive_current_variants as reader
from test_amendment_passes import rows,record,REVERSE,DIAGRAM,FASTENERS
from test_amendment_integration import assess,checkpoint


def trace(passes):
    candidates=(0,1);wrong=[]
    for rank,index in enumerate(i for order in passes for i in order):
        candidates,bad=rules.loosening_step(candidates,rank,f'p{index}',FASTENERS,consistent=True)
        if bad:wrong.append(rank+1)
    return wrong


class Amendment2(unittest.TestCase):
    def test_only_two_of_eight_documented_pass_combinations_are_consistent(self):
        for passes in product((REVERSE,DIAGRAM),repeat=3):
            expected=len(set(passes))==1
            self.assertEqual(rules.documented_loosening(rows(passes),rows((REVERSE,)*3),FASTENERS,same_loosening,consistent=True),expected)
            value=assess(record(passes),rules.AMENDMENT2)
            self.assertEqual(checkpoint(value,'CP04')['passed'],expected)
            self.assertEqual(value['primary_score']['points_earned'],18 if expected else 17)
            self.assertEqual(value['mistakes']['by_type'].get('wrong_order',0),len(trace(passes)))

    def test_valid_prefix_and_prior_violation_are_not_reset_between_passes(self):
        for order in (REVERSE,DIAGRAM):
            for n in range(1,11):self.assertEqual(trace((order,order[:n])),[])
        self.assertEqual(trace((DIAGRAM,REVERSE,DIAGRAM)),[16,18])
        invalid=(10,9,8,7,6,1,4,5,2,1)
        self.assertEqual(trace((invalid,REVERSE,DIAGRAM)),[6,16,18])

    def test_host_selection_distinguishes_withdrawn_and_current_rules(self):
        r=record((DIAGRAM,REVERSE,DIAGRAM));r['checkpoint_revision']=rules.AMENDMENT1
        # This authored helper's rechain handles the raw action commitments.
        old=assess(deepcopy(r),rules.AMENDMENT1);new=assess(r,rules.AMENDMENT2)
        self.assertEqual(old['primary_score']['points_earned'],18)
        self.assertEqual(new['primary_score']['points_earned'],17)
        self.assertEqual(new['checkpoint_revision'],rules.AMENDMENT2)
        self.assertEqual(new['primary_score']['checkpoint_revision'],rules.AMENDMENT2)

    def test_cover_reuse_and_mandatory_new_head_gasket_remain(self):
        for order in (REVERSE,DIAGRAM):
            value=assess(record((order,)*3),rules.AMENDMENT2)
            self.assertTrue(checkpoint(value,'CP08')['passed'])
            self.assertTrue(checkpoint(value,'CP12')['passed'])
            self.assertEqual(value['mistakes']['by_type'].get('wrong_order',0),0)

    def test_changed_increment_and_missing_complete_pass_refuse(self):
        expected=rows((REVERSE,)*3);actual=rows((DIAGRAM,)*3)
        self.assertFalse(rules.documented_loosening(actual[:-1],expected,FASTENERS,same_loosening,consistent=True))
        actual[10]['angle_deg']=-60
        self.assertFalse(rules.documented_loosening(actual,expected,FASTENERS,same_loosening,consistent=True))

    def test_batch_helper_forwards_current_host_choice(self):
        from test_checkpoint_chronology import rechain
        r=rechain(record((DIAGRAM,REVERSE,DIAGRAM)))
        value=reader.assess_case(r,rules.AMENDMENT2)
        self.assertEqual(value['checkpoint_revision'],rules.AMENDMENT2)
        self.assertFalse(checkpoint(value,'CP04')['passed'])


if __name__=='__main__':unittest.main()
