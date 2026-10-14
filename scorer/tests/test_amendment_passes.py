"""Coordinator per-pass ruling, exercised with authored values only."""
from copy import deepcopy
from itertools import product
import unittest

from job_accuracy.checkpoint_contracts import documented_loosening,loosening_step,ORIGINAL
from job_accuracy.checkpoints import same_loosening
from test_amendment_integration import assess,benchmark,checkpoint

REVERSE=(10,9,8,7,6,5,4,3,2,1)
DIAGRAM=(10,9,8,7,6,3,4,5,2,1)
FASTENERS={f'p{i}':{'group':'head','sequence_index':i} for i in range(1,11)}


def rows(passes):
    return [{'part_id':f'p{i}','mode':'loosen','angle_deg':-120} for order in passes for i in order]


def record(passes):
    r=benchmark()
    selected=[a for a in r['actions'] if a['name']=='torque' and a['input'].get('mode')=='loosen'
              and a['input'].get('part_id','').startswith('hb')]
    for action,index in zip(selected,[i for order in passes for i in order]):
        action['input']['part_id']=f'hb{index:02}'
    return r


def trace(passes):
    candidates=(0,1);wrong=[]
    for rank,index in enumerate(i for order in passes for i in order):
        candidates,error=loosening_step(candidates,rank,f'p{index}',FASTENERS)
        if error:wrong.append(rank+1)
    return wrong


class PerPassRuling(unittest.TestCase):
    def test_all_eight_documented_three_pass_choices(self):
        expected=rows((REVERSE,)*3)
        for passes in product((REVERSE,DIAGRAM),repeat=3):
            self.assertTrue(documented_loosening(rows(passes),expected,FASTENERS,same_loosening),passes)
            self.assertEqual(trace(passes),[],passes)

    def test_inter_pass_change_has_primary_credit_without_order_penalty(self):
        for passes in ((REVERSE,DIAGRAM,REVERSE),(DIAGRAM,REVERSE,DIAGRAM)):
            r=record(passes);new=assess(deepcopy(r));old=assess(r,ORIGINAL)
            self.assertTrue(checkpoint(new,'CP04')['passed'])
            self.assertEqual(new['primary_score']['points_earned'],18)
            self.assertEqual(new['mistakes']['by_type'].get('wrong_order',0),0)
            self.assertFalse(checkpoint(old,'CP04')['passed'])
            self.assertGreater(old['mistakes']['by_type'].get('wrong_order',0),0)

    def test_within_pass_mix_remains_a_process_violation(self):
        hybrid=(10,9,8,7,6,5,4,5,2,1)
        for passes in ((hybrid,DIAGRAM,REVERSE),(DIAGRAM,hybrid,REVERSE),(DIAGRAM,REVERSE,hybrid)):
            self.assertFalse(documented_loosening(rows(passes),rows((REVERSE,)*3),FASTENERS,same_loosening))
            value=assess(record(passes))
            self.assertFalse(checkpoint(value,'CP04')['passed'])
            self.assertEqual(value['mistakes']['by_type'].get('wrong_order',0),1)

    def test_valid_prefixes_remain_free_of_order_mistakes(self):
        for first,next_order in product((REVERSE,DIAGRAM),repeat=2):
            for length in range(1,11):
                self.assertEqual(trace((first,next_order[:length])),[])

    def test_early_violation_survives_later_choice_and_next_pass_reset(self):
        invalid=(10,9,8,7,6,1,4,5,2,1)
        self.assertEqual(trace((invalid,REVERSE,DIAGRAM)),[6])
        value=assess(record((invalid,REVERSE,DIAGRAM)))
        self.assertFalse(checkpoint(value,'CP04')['passed'])
        self.assertEqual(value['mistakes']['by_type'].get('wrong_order',0),1)
        charges=[r for r in value['human_time']['ledger'] if 'wrong_order' in r['mistake_types']]
        self.assertEqual(len(charges),1)
        self.assertGreater(charges[0]['penalty_seconds'],0)

    def test_extra_complete_pass_is_redo_and_process_failure(self):
        r=record((DIAGRAM,REVERSE,DIAGRAM))
        indices=[i for i,a in enumerate(r['actions']) if a['name']=='torque' and a['input'].get('mode')=='loosen'
                 and a['input'].get('part_id','').startswith('hb')]
        extra=deepcopy([r['actions'][i] for i in indices[-10:]])
        r['actions'][indices[-1]+1:indices[-1]+1]=extra
        value=assess(r)
        self.assertFalse(checkpoint(value,'CP04')['passed'])
        self.assertEqual(value['mistakes']['by_type'].get('redo_work',0),10)

    def test_pass_choice_does_not_waive_stage_count_or_increment(self):
        actual=rows((DIAGRAM,REVERSE,DIAGRAM));expected=rows((REVERSE,)*3)
        for changed in (actual[:-1],actual+actual[:10]):
            self.assertFalse(documented_loosening(changed,expected,FASTENERS,same_loosening))
        actual[10]['angle_deg']=-60
        self.assertFalse(documented_loosening(actual,expected,FASTENERS,same_loosening))
