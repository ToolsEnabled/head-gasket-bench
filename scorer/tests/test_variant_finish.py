"""Finish classification uses action values, never a control or variant name."""
from copy import deepcopy
import unittest
from job_accuracy.finish import observe
from job_accuracy import independent as core


def example():
    config={'benchmark_task':{'variant_id':'arbitrary'},'policy':{'flatness_limit_m':0.00005,
            'flatness_limits_m':{'head_face':0.00005,'block_deck':0.00005}}}
    parts={'belt':{'role':'timing_belt'},'new_belt':{'role':'timing_belt_supply','replacement_for':'belt'}}
    final={'parts':{'belt':{'damaged':False},'new_belt':{'damaged':False}},
           'surfaces':{'head_face':{'warpage_m':0.00002},'block_deck':{'warpage_m':0.00002}},
           'timing':{'tensioned':True}}
    fasteners={'hb01':{'group':'head'}}
    history=[{'name':'measure','input':{'target':target,'kind':kind}} for target,kind in
             [('head_face','flatness'),('block_deck','flatness'),('hb01','bolt_stretch')]]
    history.append({'name':'inspect','input':{'target':'belt'}})
    return [config,final,parts,fasteners,history]


def faults():
    cases=[]
    for name in ['missed_measurement','missed_inspection','wrong_service_decision','wrong_part','missed_belt_tension']:
        args=example()
        if name=='missed_measurement':args[-1].pop(0)
        elif name=='missed_inspection':args[-1].pop()
        elif name=='wrong_service_decision':args[1]['surfaces']['head_face']['warpage_m']=0.00008
        elif name=='wrong_part':args[1]['parts']['belt']['damaged']=True
        else:args[1]['timing']['tensioned']=False
        cases.append((name,args))
    return cases


def recorded_example():
    from test_successor_components import benchmark,event
    from test_checkpoint_chronology import rechain
    r=benchmark()
    if not any(a['name']=='inspect' and a['input'].get('target')=='belt' for a in r['actions']):
        r['actions'].insert(-1,event('inspect',{'target':'belt'}))
    p=r['config']['repair_scoring']['human_time_policy'];p['base_classification']=core.CLASSIFICATION
    for i,(name,_) in enumerate(faults()):
        value=deepcopy(next(iter(p['mistakes'].values())));value['seconds']=57+i;p['mistakes'][name]=value
    return rechain(r)


def changed_record(label):
    from test_checkpoint_chronology import rechain
    r=recorded_example()
    if label in ('missed_measurement','missed_inspection'):
        name,target=('measure','head_face') if label=='missed_measurement' else ('inspect','belt')
        for a in r['actions']:
            if a['name']==name and a['input'].get('target')==target:a.update(name='look',input={})
    elif label=='wrong_service_decision':r['final_state']['surfaces']['head_face']['warpage_m']=0.00008
    elif label=='wrong_part':r['final_state']['parts']['belt']['damaged']=True
    elif label=='missed_belt_tension':r['final_state']['timing']['tensioned']=False
    return rechain(r)


def assess_record(r):
    s=r['config']['repair_scoring'];return core.assess(r,s['reference'],s['human_time_policy'])


class VariantFinish(unittest.TestCase):
    def test_completed_requirements_have_no_finish_mistake(self):
        r=observe(*example());self.assertTrue(all(v is False for v in r['mistakes'].values()))
        self.assertEqual(r['unknown_types'],[])

    def test_five_missing_or_wrong_values_are_separate_causes(self):
        for label,args in faults():
            with self.subTest(label=label):
                r=observe(*args);self.assertEqual([k for k,v in r['mistakes'].items() if v is True],[label])

    def test_service_decision_uses_each_configured_face_limit(self):
        args=example();args[0]['policy']['flatness_limits_m']['head_face']=0.00001
        self.assertTrue(observe(*args)['mistakes']['wrong_service_decision'])
        args[1]['surfaces']['head_face']['warpage_m']=0.00001
        self.assertFalse(observe(*args)['mistakes']['wrong_service_decision'])

    def test_replaced_belt_uses_current_body_but_original_inspection(self):
        args=example();args[1]['parts']['belt']['damaged']=True
        args[-1].append({'name':'replace','input':{'part_id':'belt','replacement_id':'new_belt'}})
        r=observe(*args);self.assertFalse(r['mistakes']['wrong_part']);self.assertEqual(r['detail']['active_belt'],'new_belt')
        args[1]['parts']['new_belt']['damaged']=True
        self.assertTrue(observe(*args)['mistakes']['wrong_part'])

    def test_unknown_measurements_or_boolean_spellings_remain_unknown(self):
        for value in (None,0,1,'false'):
            args=example();args[1]['parts']['belt']['damaged']=value;args[1]['timing']['tensioned']=value
            r=observe(*args);self.assertIsNone(r['mistakes']['wrong_part']);self.assertIsNone(r['mistakes']['missed_belt_tension'])
        args=example();args[1]['surfaces']['head_face']['warpage_m']=None
        self.assertIsNone(observe(*args)['mistakes']['wrong_service_decision'])
        args[1]['surfaces']['block_deck']['warpage_m']=0.001
        self.assertTrue(observe(*args)['mistakes']['wrong_service_decision'])

    def test_legacy_task_does_not_invent_variant_requirements(self):
        args=example();args[0].pop('benchmark_task');args[-1]=[]
        self.assertEqual(observe(*args),{'mistakes':{},'detail':{},'unknown_types':[]})

    def test_variant_title_does_not_determine_mistakes(self):
        args=faults()[0][1];first=observe(*args);args[0]['benchmark_task']['variant_id']='correct'
        self.assertEqual(observe(*args),first)

    def test_five_causes_reach_actual_finish_ledger_once(self):
        for label,_ in faults():
            with self.subTest(label=label):
                record=changed_record(label);result=assess_record(record)
                event=result['mistakes']['events'][-1];self.assertIn(label,event['types'])
                self.assertEqual(result['mistakes']['by_type'][label],1)
                charge=result['human_time']['ledger'][-1];policy=record['config']['repair_scoring']['human_time_policy']
                base=policy['actions']['finish']['seconds'];wrong=label in core.WRONG_WORK
                self.assertEqual(charge['productive_seconds'],0 if wrong else base)
                self.assertEqual(charge['penalty_seconds'],policy['mistakes'][label]['seconds']+(base if wrong else 0))

    def test_unfinished_record_has_no_finish_assessment(self):
        from test_checkpoint_chronology import rechain
        r=changed_record('wrong_part');r['actions']=[a for a in r['actions'] if a['name']!='finish'];r['finished']=False
        value=assess_record(rechain(r));self.assertEqual(value['finish_observations'],[])
        self.assertNotIn('wrong_part',value['mistakes']['by_type'])

    def test_finish_is_terminal_but_later_refusals_remain_attempts(self):
        from test_successor_components import event
        from test_checkpoint_chronology import rechain
        for name in ('look','finish'):
            r=recorded_example();r['actions'].append(event(name,{}))
            with self.assertRaisesRegex(core.AssessmentInputError,'successful-action-after-finish'):
                assess_record(rechain(r))
        r=recorded_example();row=event('look',{});row['result']={'ok':False,'error':'Job has ended'}
        r['actions'].append(row);value=assess_record(rechain(r))
        self.assertEqual(value['tool_calls']['refused'],1)
        self.assertEqual(len(value['finish_observations']),1)
        self.assertEqual(value['status'],'finished')

    def test_unobserved_finish_fault_is_not_a_zero_penalty_claim(self):
        from test_checkpoint_chronology import rechain
        r=recorded_example();r['final_state']['timing']['tensioned']=None
        value=assess_record(rechain(r));self.assertIsNone(value['human_time']['penalty_seconds'])
        self.assertIsNone(value['human_time']['total_seconds'])
        self.assertEqual(value['human_time']['unobserved_finish_mistake_types'][-1]['types'],['missed_belt_tension'])

    def test_unknown_wrong_work_preserves_base_cost_without_guessing_allocation(self):
        from test_checkpoint_chronology import rechain
        from job_accuracy.report import run_report,summary
        r=recorded_example();r['final_state']['parts']['belt']['damaged']=None
        value=assess_record(rechain(r));h=value['human_time'];last=h['ledger'][-1]
        self.assertIsNone(h['productive_seconds']);self.assertIsNone(last['productive_seconds'])
        self.assertIsNone(h['total_seconds']);self.assertIsNone(h['penalty_seconds'])
        self.assertEqual(h['base_charge_without_known_allocation_seconds'],last['base_seconds'])
        self.assertEqual(h['known_charged_subtotal_seconds'],sum(
            (row['productive_seconds'] if row['productive_seconds'] is not None else row['base_seconds'])+row['known_penalty_seconds'] for row in h['ledger']))
        self.assertIn('Finish observations cannot establish: wrong part',summary(run_report(value)))

    def test_legacy_labor_keeps_known_productive_base_with_unknown_fault(self):
        from test_checkpoint_chronology import rechain
        r=recorded_example();r['config']['repair_scoring']['human_time_policy']['base_classification']=None
        r['final_state']['parts']['belt']['damaged']=None
        value=assess_record(rechain(r));h=value['human_time'];last=h['ledger'][-1]
        self.assertEqual(last['productive_seconds'],last['base_seconds'])
        self.assertEqual(h['productive_seconds'],sum(row['productive_seconds'] for row in h['ledger']))
        self.assertEqual(h['base_charge_without_known_allocation_seconds'],0)
        self.assertIsNone(h['penalty_seconds']);self.assertIsNone(h['total_seconds'])

    def test_current_complete_v1_needs_no_new_finish_label(self):
        import json
        from pathlib import Path
        r=json.loads(Path('evidence/job-accuracy/current-v1-reduction1/INPUT.json').read_bytes())
        parts={p['id']:p for p in r['config']['geometry']['parts']}
        fasteners={f['id']:f for f in r['config']['geometry']['fasteners']}
        value=observe(r['config'],r['final_state'],parts,fasteners,r['final_state']['action_history'])
        self.assertFalse(any(value['mistakes'].values()));self.assertEqual(value['unknown_types'],[])


if __name__=='__main__':unittest.main()
