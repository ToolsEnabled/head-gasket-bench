"""Authored repair-contract values; no environment execution or physical claim."""
from copy import deepcopy
import unittest
from test_checkpoint_chronology import base,rechain
from tools.test_repair_checkpoints import evaluate
from job_accuracy import independent as core


def event(name,args,observation=None):
    return {'name':name,'input':args,'result':{'ok':True,**({'observation':observation} if observation is not None else {})}}


def benchmark():
    r=base();c=r['config'];f=r['final_state']
    c['benchmark_task']={'schema':'authored-successor-value/v1','accepted_head_recovery':['machine_head','replace']}
    f['service_replacements']={}
    for original,stock,role in [('head','authored_head','head_supply'),('belt','authored_belt','timing_belt_supply')]:
        part=deepcopy(next(p for p in c['geometry']['parts'] if p['id']==original))
        part.update(id=stock,role=role,installed=False,replacement_for=original)
        c['geometry']['parts'].append(part)
        for state in (f,c['repair_scoring']['reference']['final']):
            state['parts'][stock]={'location':'supply','damaged':False}
    r['actions'].insert(0,event('set_timing',{'cam_phase_deg':0,'crank_phase_deg':0}))
    last=max(i for i,a in enumerate(r['actions']) if a['name']=='check_timing')
    r['actions'].insert(last,event('tension_belt',{'part_id':'belt'}))
    rechain(r)
    install=max(a['seq'] for a in r['actions'] if a['name']=='install' and a['input'].get('part_id')=='belt')
    tension=max(a['seq'] for a in r['actions'] if a['name']=='tension_belt')
    f['timing'].update(belt_id='belt',installed_seq=install,tensioned=True,belt_tensioned=True,tensioned_seq=tension)
    return rechain(r)


def checked(r,ident):
    value=evaluate(rechain(r))
    return next(row for row in value['primary_score']['checkpoints'] if row['id']==ident)


def repair_head(r,mode):
    rows=r['actions'];measure=next(a for a in rows if a['name']=='measure' and a['input'].get('target')=='head_face' and a['input'].get('kind')=='flatness')
    measure['result']['observation']['value']=0.00008
    index=rows.index(measure)+1
    if mode=='machine_head':
        change=event('machine_head',{'part_id':'head'})
    else:
        change=event('replace',{'part_id':'head','replacement_id':'authored_head'})
        next(a for a in rows if a['name']=='install' and a['input'].get('part_id')=='head')['input']['part_id']='authored_head'
        r['final_state']['parts']['head']['location']='waste'
        r['final_state']['parts']['authored_head']['location']='assembly'
        r['final_state']['service_replacements']={'head':'authored_head'}
    after=deepcopy(measure);after['result']['observation']['value']=0.00002
    rows[index:index]=[change,after]
    rechain(r)
    # These inserted authored rows precede the later timing work.
    r['final_state']['timing']['installed_seq']=max(a['seq'] for a in rows if a['name']=='install' and a['input'].get('part_id')=='belt')
    r['final_state']['timing']['tensioned_seq']=max(a['seq'] for a in rows if a['name']=='tension_belt')
    return rechain(r)


class SuccessorComponents(unittest.TestCase):
    def test_complete_authored_contract_is_eighteen_points(self):
        self.assertEqual(evaluate(benchmark())['primary_score']['points_earned'],18)

    def test_explicit_setup_before_observation_is_required(self):
        r=benchmark();r['actions'][0]['input']['cam_phase_deg']=1
        self.assertFalse(checked(r,'CP03')['passed'])

    def test_phase_setup_after_precheck_invalidates_tdc_credit(self):
        r=benchmark();index=next(i for i,a in enumerate(r['actions']) if a['name']=='remove' and a['input'].get('part_id')=='belt')
        r['actions'].insert(index,event('set_timing',{'cam_phase_deg':10,'crank_phase_deg':0}))
        self.assertFalse(checked(r,'CP03')['passed'])

    def test_tension_event_is_current_and_flags_cannot_substitute(self):
        r=benchmark();a=next(a for a in r['actions'] if a['name']=='tension_belt');a['name']='look';a['input']={}
        self.assertFalse(checked(r,'CP11')['passed'])

    def test_phase_setup_after_last_check_cancels_credit(self):
        r=benchmark();r['actions'].insert(-1,event('set_timing',{'cam_phase_deg':0,'crank_phase_deg':0}))
        self.assertFalse(checked(r,'CP11')['passed'])

    def test_latest_short_check_does_not_borrow_prior_rotations(self):
        r=benchmark();r['actions'].insert(-1,event('check_timing',{'crank_revolutions':1},{'marks_align':True}))
        self.assertFalse(checked(r,'CP11')['passed'])

    def test_machined_or_replaced_head_has_current_measurement(self):
        for mode in ('machine_head','replace'):
            with self.subTest(mode=mode):
                r=repair_head(benchmark(),mode)
                self.assertTrue(checked(r,'CP06')['passed'])
                self.assertTrue(checked(r,'CP12')['passed'])
                self.assertEqual(evaluate(r)['primary_score']['points_earned'],18)

    def test_recovery_without_prior_measurement_does_not_pass(self):
        r=repair_head(benchmark(),'machine_head')
        measure=next(a for a in r['actions'] if a['name']=='measure' and a['input'].get('target')=='head_face' and a['input'].get('kind')=='flatness')
        measure['name']='look';measure['input']={}
        self.assertFalse(checked(r,'CP06')['passed'])

    def test_over_limit_value_cannot_be_fixed_only_in_final_state(self):
        r=benchmark();a=next(a for a in r['actions'] if a['name']=='measure' and a['input'].get('target')=='head_face' and a['input'].get('kind')=='flatness')
        a['result']['observation']['value']=0.00008
        self.assertFalse(checked(r,'CP06')['passed'])

    def test_repair_without_post_service_measurement_does_not_pass(self):
        r=repair_head(benchmark(),'machine_head')
        measures=[a for a in r['actions'] if a['name']=='measure' and a['input'].get('target')=='head_face' and a['input'].get('kind')=='flatness']
        measures[-1]['name']='look';measures[-1]['input']={}
        self.assertFalse(checked(r,'CP06')['passed'])

    def test_unnecessary_remedy_is_not_a_correct_measured_decision(self):
        r=repair_head(benchmark(),'machine_head')
        next(a for a in r['actions'] if a['name']=='measure' and a['input'].get('target')=='head_face')['result']['observation']['value']=0.00002
        self.assertFalse(checked(r,'CP06')['passed'])

    def test_replacement_position_and_reported_binding_are_authenticated(self):
        r=repair_head(benchmark(),'replace')
        r['final_state']['service_replacements']={}
        with self.assertRaisesRegex(core.AssessmentInputError,'component-replacement-state'):evaluate(rechain(r))
        r=repair_head(benchmark(),'replace')
        next(p for p in r['config']['geometry']['parts'] if p['id']=='authored_head')['replacement_for']='belt'
        with self.assertRaisesRegex(core.AssessmentInputError,'component-replacement-position'):evaluate(rechain(r))

    def test_discarded_original_is_not_allowed_back_beside_replacement(self):
        r=repair_head(benchmark(),'replace');r['final_state']['parts']['head']['location']='assembly'
        self.assertFalse(checked(r,'CP12')['passed'])

if __name__=='__main__':unittest.main()
