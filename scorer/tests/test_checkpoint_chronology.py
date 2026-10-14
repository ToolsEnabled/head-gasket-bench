"""Authored chronology values; no claimed execution of impossible actions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from tools.test_repair_checkpoints import commit,evaluate
from job_accuracy.independent import fingerprint

ROOT=Path(__file__).resolve().parents[1]


def base():
    value=json.loads((ROOT/'evidence/job-accuracy/checkpoint-values1/AUTHORED-COMPLETE-VALUE-FIXTURE.json').read_bytes())
    # Explicit authored successor stock from the signed checkpoint contract.
    next(p for p in value['config']['geometry']['parts'] if p['role']=='gasket_new')['catalog']['bore_mm']=75
    return value


def rechain(record):
    previous=fingerprint({'authored_state':0})
    for index,row in enumerate(record['actions'],1):
        row['seq']=index;row['pre_state_sha256']=previous
        previous=fingerprint({'authored_state':index});row['post_state_sha256']=previous
    return commit(record)


def primary(record,ident):
    result=evaluate(rechain(record))
    return next(r for r in result['primary_score']['checkpoints'] if r['id']==ident)['passed']


class Chronology(unittest.TestCase):
    def test_cleanup_after_closure_does_not_earn_credit(self):
        r=base();a=r['actions'];row=next(x for x in a if x['name']=='clean' and x['input'].get('target')=='head_face')
        a.remove(row);a.insert(-1,row)
        self.assertFalse(primary(r,'CP05'))

    def test_only_measurement_after_replacement_is_not_a_decision_witness(self):
        r=base();a=r['actions'];row=next(x for x in a if x['name']=='measure' and x['input'].get('target')=='hb03')
        a.remove(row);decision=next(i for i,x in enumerate(a) if x['name']=='replace' and x['input'].get('part_id')=='hb03')
        a.insert(decision+1,row)
        self.assertFalse(primary(r,'CP07'))

    def test_later_extra_measurement_does_not_erase_earlier_valid_witness(self):
        r=base();a=r['actions'];row=next(x for x in a if x['name']=='measure' and x['input'].get('target')=='hb03')
        a.insert(-1,deepcopy(row))
        self.assertTrue(primary(r,'CP07'))


if __name__=='__main__':unittest.main()
