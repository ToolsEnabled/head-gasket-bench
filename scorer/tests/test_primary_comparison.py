"""Fieldwise primary values; metadata never changes the scoring agreement."""
from copy import deepcopy
import unittest
from job_accuracy.checkpoints import DEFINITIONS
from job_accuracy.comparison import compare_primary


def primary():
    rows=[{'id':ident,'weight':weight,'title':'Authored label','passed':True,'requirements':{'observed':True},'not_met':[],
           'evidence_sequences':[1]} for ident,weight,_ in DEFINITIONS]
    return {'checkpoints':rows,'points_earned':18,'total_points':18,'S_full':1,'S_partial':1.0}


def compare(value):return compare_primary(primary(),value,DEFINITIONS,2)


class PrimaryComparison(unittest.TestCase):
    def test_exact_semantics_ignore_label_wording(self):
        p=primary();p['interface_status']='Other wording';p['checkpoints'][0]['title']='Different title'
        r=compare(p);self.assertEqual(r['status'],'agreement');self.assertFalse(r['contract_identity_authenticated'])

    def test_outcome_changes_get_fieldwise_differences(self):
        p=primary();r=p['checkpoints'][1];r.update(passed=False,requirements={'observed':False},not_met=['observed'])
        p.update(points_earned=16,S_full=0,S_partial=16/36)
        value=compare(p);self.assertEqual(value['status'],'disagreement')
        self.assertIn('CP02/passed',[d['field'] for d in value['disagreements']])

    def test_refused_attempt_indices_and_different_requirements_are_separate(self):
        p=primary();p['checkpoints'][1]['evidence_sequences']=[2];p['checkpoints'][1]['requirements']={'other_witness':True}
        value=compare(p);self.assertEqual(value['status'],'agreement');self.assertEqual(len(value['evidence_differences']),2)

    def test_null_producer_does_not_invent_agreement(self):
        self.assertEqual(compare(None)['status'],'unavailable')

    def test_each_structural_corruption_is_refused(self):
        mutations=[('comparison-checkpoint-census',lambda p:p['checkpoints'].pop()),
          ('comparison-checkpoint-values',lambda p:p['checkpoints'][0].update(passed=1)),
          ('comparison-requirements',lambda p:p['checkpoints'][0].update(requirements={})),
          ('comparison-checkpoint-evidence',lambda p:p['checkpoints'][0].update(not_met=['invented'])),
          ('comparison-evidence-indices',lambda p:p['checkpoints'][0].update(evidence_sequences=[True])),
          ('comparison-primary-arithmetic',lambda p:p.update(S_full=True))]
        for code,change in mutations:
            p=primary();change(p)
            with self.subTest(code=code):self.assertEqual(compare(p).get('reason'),code)

    def test_unknown_requirements_fail_binary_credit(self):
        p=primary();p['checkpoints'][0]['requirements']['observed']=None
        self.assertEqual(compare(p).get('reason'),'comparison-checkpoint-evidence')
        p['checkpoints'][0].update(passed=False,not_met=['observed']);p.update(points_earned=17,S_full=0,S_partial=17/36)
        self.assertEqual(compare(p)['status'],'disagreement')

if __name__=='__main__':unittest.main()
