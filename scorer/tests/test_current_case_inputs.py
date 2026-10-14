"""A batch label does not establish its variant, start or recovery route."""
from copy import deepcopy
import unittest
from tools import receive_current_variants as reader
from job_accuracy.independent import AssessmentInputError


def example():
    row={'variant':'V3','control':'correct','head_recovery':'replace'}
    record={'config':{'variant_id':'V3','factors':{'turn_budget':1024,'turn_budget_unit':'job-tool-action-attempts'},
                      'geometry':{'parts':[{'id':'head','role':'head'}]}},
            'final_state':{'action_history':[{'name':'replace','input':{'part_id':'head','replacement_id':'new_head'}}]}}
    value={'initial_evidence':{'available':True,'budget_checked':True}}
    return row,record,value


def negatives():
    rows=[]
    for label in ('variant','missing-start','missing-budget','different-limit','boolean-limit','unit','same-machine-route','both-routes'):
        row,r,v=example();gate='batch-current-start'
        if label=='variant':r['config']['variant_id']='V1';gate='batch-variant-binding'
        elif label=='missing-start':v['initial_evidence']['available']=False
        elif label=='missing-budget':v['initial_evidence']['budget_checked']=False
        elif label=='different-limit':r['config']['factors']['turn_budget']=512
        elif label=='boolean-limit':r['config']['factors']['turn_budget']=True
        elif label=='unit':r['config']['factors']['turn_budget_unit']='model-turns'
        elif label=='same-machine-route':r['final_state']['action_history'][0]['name']='machine_head';gate='batch-recovery-binding'
        else:r['final_state']['action_history'].append({'name':'machine_head','input':{'part_id':'head'}});gate='batch-recovery-binding'
        rows.append((label,gate,(row,r,v)))
    return rows


class CurrentCaseInputs(unittest.TestCase):
    def test_both_declared_v3_routes_use_distinct_actual_operations(self):
        args=example();self.assertEqual(reader.case_inputs(*args),['replace'])
        args[0]['head_recovery']='machine';args[1]['final_state']['action_history'][0]['name']='machine_head'
        self.assertEqual(reader.case_inputs(*args),['machine_head'])

    def test_coherent_labels_do_not_replace_received_evidence(self):
        for label,gate,args in negatives():
            with self.subTest(label=label),self.assertRaisesRegex(AssessmentInputError,gate):reader.case_inputs(*args)

    def test_ordinary_variant_does_not_claim_head_machining(self):
        row,r,v=example();row['variant']=r['config']['variant_id']='V1';row['head_recovery']='machine';r['final_state']['action_history']=[]
        self.assertEqual(reader.case_inputs(row,r,v),[])

    def test_analysis_completion_with_any_disagreement_is_not_acceptance(self):
        rows=[{'expected_control_behavior':True,'primary_comparison':{'status':'agreement'},
               'producer_comparison':{'status':'disagreement','disagreements':[],
                   'independent_only_items':['unobserved-condition'],'producer_only_items':['restoration-rule']}}
              for _ in range(13)]
        self.assertTrue(reader.classification(rows)['accepted'])
        for change in ('missing','wrong-behavior','disagreement','invalid-comparison','time-mismatch','missing-secondary'):
            values=deepcopy(rows)
            if change=='missing':values.pop()
            elif change=='wrong-behavior':values[0]['expected_control_behavior']=False
            elif change=='time-mismatch':values[0]['producer_comparison']['disagreements']=[{'field':'human_time/penalty_seconds','independent':60,'producer':0}]
            elif change=='missing-secondary':values[0]['producer_comparison']={'status':'unavailable','disagreements':[]}
            else:values[0]['primary_comparison']['status']=change
            got=reader.classification(values);self.assertFalse(got['accepted']);self.assertEqual(got['status'],'RECEIVED_WITH_DISAGREEMENTS')

if __name__=='__main__':unittest.main()
