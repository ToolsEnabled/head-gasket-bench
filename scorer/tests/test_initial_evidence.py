"""Value tests for exact exported starts, empty prefixes and budget receipts."""
from copy import deepcopy
import unittest
from job_accuracy.independent import fingerprint, AssessmentInputError
from job_accuracy.inputs import initial_evidence, MECHANICAL_KEYS


def example(count=1):
    config={'variant_id':'authored', 'geometry':{'parts':[{'id':'head','installed':True},
            {'id':'stock','installed':False,'available_in_bin':False}]}, 'benchmark_task':{},
            'factors':{'turn_budget_unit':'job-tool-action-attempts','turn_budget':2},
            'benchmark_removal':{'policy_sha256':'authored-raw-policy',
             'policy':{'release_actions':['thread'], 'condition_ids':['cold']}}}
    # Nonempty benchmark declaration activates the stock availability rule.
    config['benchmark_task']={'scope':'authored'}
    initial={'identity':{'config_sha256':fingerprint(config)},'variant_id':'authored','revision':0,
             'parts':{'head':{'location':'assembly'},'stock':{'location':'unavailable'}},
             'bolts':{},'surfaces':{},'gasket':{},'timing':{},'action_history':[],
             'service_receipts':[],'service_replacements':{},
             'benchmark_removal':{'policy_sha256':'authored-raw-policy','physical_qualification':False,
                'released':{'thread':False},'conditions':{'cold':False},'replacements':{},
                'movements':[],'attachment_history':[]}}
    r={'config':config,'config_sha256':fingerprint(config),'initial_state':initial,
       'actions':[{'pre_state_sha256':fingerprint(initial)} for _ in range(count)],
       'budget':{'unit':'job-tool-action-attempts','limit':2,'used':min(count,2),
                 'attempted_calls':count,'exhausted':count>=2}}
    return seal(r)


def seal(r):
    initial=r['initial_state'];pin=fingerprint(initial)
    r['initial_state_sha256']=pin;r['final_state_sha256']=pin
    if r['actions']:r['actions'][0]['pre_state_sha256']=pin
    ref={'initial_sha256':fingerprint({k:initial[k] for k in MECHANICAL_KEYS})}
    return r,ref


def cases():
    rows=[]
    def add(gate, change, reseal=False):
        r,ref=example();change(r,ref)
        if reseal:r,ref=seal(r)
        rows.append((gate,r,ref))
    def wrong_raw_commitment(r,f):
        r['initial_state_sha256']='wrong';r['actions'][0]['pre_state_sha256']='wrong'
    add('initial-state-commitment',wrong_raw_commitment)
    add('initial-config-binding',lambda r,f:r['initial_state']['identity'].update(config_sha256='other'),True)
    add('initial-empty-history',lambda r,f:r['initial_state'].update(revision=True),True)
    add('initial-empty-history',lambda r,f:r['initial_state']['service_receipts'].append({'operation':'old'}),True)
    add('initial-reference-projection',lambda r,f:f.update(initial_sha256='other'))
    add('initial-journal-join',lambda r,f:r['actions'][0].update(pre_state_sha256='other'))
    add('initial-location-binding',lambda r,f:r['initial_state']['parts']['head'].update(location='tray'),True)
    add('initial-removal-baseline',lambda r,f:r['initial_state']['benchmark_removal']['released'].update(thread=True),True)
    add('initial-removal-baseline',lambda r,f:r['initial_state']['benchmark_removal']['conditions'].update(cold=0),True)
    add('initial-budget-presence',lambda r,f:r.pop('budget'))
    add('initial-budget-accounting',lambda r,f:r['budget'].update(limit=1,used=1,exhausted=True))
    add('initial-budget-accounting',lambda r,f:r['budget'].update(used=True))
    add('initial-budget-accounting',lambda r,f:r['budget'].update(unit='model-turns'))
    return rows


class InitialEvidence(unittest.TestCase):
    def test_empty_partial_and_budget_exhausted_are_received(self):
        for count in (0,1,2,3):
            r,ref=example(count);value=initial_evidence(r,ref)
            self.assertTrue(value['available']);self.assertTrue(value['first_action_or_empty_final_joined'])
            self.assertFalse(value['runtime_source_authenticated'])

    def test_old_record_has_explicit_missing_status(self):
        self.assertEqual(initial_evidence({},{}),{'available':False,'reason':'Repair-start state was not supplied',
                                                'runtime_source_authenticated':False})

    def test_corruptions_refuse_the_specific_boundary(self):
        for gate,r,ref in cases():
            with self.subTest(gate=gate),self.assertRaisesRegex(AssessmentInputError,gate):initial_evidence(r,ref)

    def test_empty_record_still_binds_final_to_initial(self):
        r,ref=example(0);r['final_state_sha256']='different'
        with self.assertRaisesRegex(AssessmentInputError,'initial-journal-join'):initial_evidence(r,ref)

    def test_absent_half_of_pair_is_not_legacy_missing(self):
        r,ref=example();del r['initial_state_sha256']
        with self.assertRaisesRegex(AssessmentInputError,'initial-state-commitment'):initial_evidence(r,ref)

if __name__=='__main__':unittest.main()
