"""Refused removal and engaged-thread value boundaries, no environment calls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from job_accuracy import checkpoints, independent
from tools.test_repair_checkpoints import commit, evaluate

ROOT=Path(__file__).resolve().parents[1]


def refused(name,inputs):
    record=json.loads((ROOT/'evidence/job-accuracy/checkpoint-values1/AUTHORED-COMPLETE-VALUE-FIXTURE.json').read_bytes())
    # Explicit successor stock value; the retained authored draft used 75.5 mm.
    next(p for p in record['config']['geometry']['parts'] if p['role']=='gasket_new')['catalog']['bore_mm']=75
    record['actions'][1].update(name=name,input=inputs,result={'ok':False,'refusal':'Authored refusal; classification must use values'})
    return commit(record)


class RemovalBoundary(unittest.TestCase):
    def test_engaged_removal_fails_primary_and_counts_blocked(self):
        result=evaluate(refused('remove',{'part_id':'cb01'}))
        cp=next(r for r in result['primary_score']['checkpoints'] if r['id']=='CP02')
        self.assertFalse(cp['passed'])
        self.assertEqual(result['primary_score']['S_full'],0)
        self.assertEqual(result['mistakes']['by_type'],{'blocked_removal':1})
        self.assertEqual(result['mistakes']['events'][0]['detail']['engagement_turns'],1)

    def test_other_refusals_do_not_automatically_fail_disassembly(self):
        result=evaluate(refused('look',{}))
        self.assertTrue(next(r for r in result['primary_score']['checkpoints'] if r['id']=='CP02')['passed'])
        self.assertEqual(result['primary_score']['S_full'],1)
        self.assertEqual(result['mistakes']['by_type'],{'invalid_action':1})

    def test_engagement_values_are_typed_and_do_not_invent_unknowns(self):
        for value in (1,0.25,2e-9):
            with self.subTest(value=value):self.assertTrue(independent.blocked_removal([],[],value))
        for value in (0,1e-10,None,True):
            with self.subTest(value=value):self.assertFalse(independent.blocked_removal([],[],value))
        self.assertTrue(independent.blocked_removal(['head'],[],None))
        self.assertTrue(independent.blocked_removal([],['bolt'],None))


if __name__=='__main__':unittest.main()
