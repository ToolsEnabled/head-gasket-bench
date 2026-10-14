"""Authored successor input values; no environment or in-game scorer calls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from job_accuracy import independent as core
from job_accuracy.checkpoints import score

ROOT=Path(__file__).resolve().parents[1]

def base():
    return json.loads((ROOT/'evidence/job-accuracy/seven-inputs1/correct.json').read_bytes())

def reseal(r):
    c=r['config'];reference=c['repair_scoring']['reference']
    reference['geometry_sha256']=core.fingerprint(c['geometry'])
    c['repair_scoring']['reference_sha256']=core.fingerprint(reference)
    r['config_sha256']=core.fingerprint(c)
    r['final_state']['identity']['action_history_sha256']=core.fingerprint(r['final_state']['action_history'])
    r['final_state_sha256']=core.fingerprint(r['final_state'])
    r['actions'][-1]['post_state_sha256']=r['final_state_sha256']
    previous=r['config_sha256']
    for row in r['actions']:
        row['previous_action_sha256']=previous;previous=core.fingerprint(row)
    return r

def run(r):
    settings=r['config']['repair_scoring']
    return score(reseal(r),settings['reference'],settings['human_time_policy'])

def stock_label(c,pid):
    return 'stock_'+core.fingerprint({'body_id':pid,'variant':c['variant_id']})[:12]

def with_retained():
    r=base();c=r['config'];f=r['final_state'];ref=c['repair_scoring']['reference']
    part=deepcopy(next(p for p in c['geometry']['parts'] if p['id']=='cb01'))
    part.update(id='authored_retained_fastener',role='retained_fastener',installed=True)
    c['geometry']['parts'].append(part)
    fastener=deepcopy(next(x for x in c['geometry']['fasteners'] if x['id']=='cb01'))
    fastener.update(id=part['id'],group='retained_only',service_required=False,sequence_index=None,
                    torque_spec_N_m=None,initial_engagement_turns=None,holds=[])
    c['geometry']['fasteners'].append(fastener)
    for state in (f,ref['final']):
        state['parts'][part['id']]={'location':'assembly','damaged':None}
        state['bolts'][part['id']]={'torque_N_m':None,'stretch_mm':None,'turns':None}
    return r

class SuccessorInputs(unittest.TestCase):
    def test_original_saved_job_is_unchanged(self):
        a=run(base());self.assertEqual(a['bolt_accuracy']['correct'],60)
        self.assertEqual(a['checklist_accuracy']['correct'],316)
        self.assertEqual(a['human_time']['total_seconds'],5860)

    def test_all_original_stock_aliases_join_to_successful_history(self):
        r=base();c=r['config'];c['benchmark_task']={'schema':'authored-input-value/v1'}
        supply={p['id'] for p in c['geometry']['parts'] if p['installed'] is False}
        for row in r['actions']:
            for key,value in list(row['input'].items()):
                if key in ('part_id','replacement_id','target') and value in supply:
                    row['input'][key]=stock_label(c,value)
        a=run(r)
        self.assertEqual(a['bolt_accuracy']['correct'],60)
        self.assertEqual(a['checklist_accuracy']['correct'],316)
        current=next(b for b in a['bolt_accuracy']['bolts'] if b['sequence_index']==3)
        self.assertEqual(current['body_id'],'new_hb03')

    def test_alias_variant_and_original_installation_are_significant(self):
        c=base()['config'];c['benchmark_task']={'schema':'authored-input-value/v1'}
        aliases=core.public_body_map(c)
        self.assertEqual(aliases[stock_label(c,'new_hb03')],'new_hb03')
        self.assertEqual(aliases['hb03'],'hb03')
        c['variant_id']='authored_other_variant';other=core.public_body_map(c)
        self.assertNotEqual(aliases,other)
        self.assertNotIn(stock_label(c,'hb03'),other)

    def test_alias_collision_has_named_refusal(self):
        c=base()['config'];target=next(p for p in c['geometry']['parts'] if p['role']=='gasket_new')
        c['geometry']['parts'].append({'id':stock_label(c,target['id']),'role':'block','installed':True})
        with self.assertRaisesRegex(core.AssessmentInputError,'public-alias-census'):
            core.public_body_map(c)

    def test_retained_null_fastener_does_not_require_service(self):
        a=run(with_retained())
        self.assertEqual(a['bolt_accuracy']['correct'],60)
        self.assertEqual(a['human_time']['total_seconds'],5860)
        self.assertEqual(a['coverage']['retained_fasteners_without_stage_requirements'],['authored_retained_fastener'])
        self.assertFalse(any(i['item'].startswith('fastener/authored_retained_fastener/') for i in a['checklist_accuracy']['items']))
        cp=next(row for row in a['primary_score']['checkpoints'] if row['id']=='CP12')
        self.assertTrue(cp['passed'])
        unknown=next(row for row in a['checklist_accuracy']['items'] if row['item']=='part/authored_retained_fastener/undamaged')
        self.assertIsNone(unknown['correct'])

    def test_service_flag_is_plain_boolean(self):
        for value in (None,0,1,'false'):
            with self.subTest(value=value),self.assertRaisesRegex(core.AssessmentInputError,'service-required-domain'):
                core.required_positions({'retained':{'service_required':value}})

    def test_retained_position_cannot_hide_a_missing_required_stage(self):
        r=with_retained();del r['config']['repair_scoring']['reference']['stages']['cb01']
        with self.assertRaisesRegex(core.AssessmentInputError,'reference-stages'):run(r)

    def test_successful_torque_on_retained_position_is_refused_explicitly(self):
        # The torque is inserted before the finish: a successful action after a
        # committed finish is refused first as 'successful-action-after-finish'.
        r=with_retained();finish=r['actions'][-1];row=deepcopy(finish);row.update(seq=finish['seq'],
            name='torque',input={'part_id':'authored_retained_fastener','mode':'tighten','value_N_m':10},
            result={'ok':True},post_state_sha256=finish['pre_state_sha256'])
        finish['seq']+=1;r['actions'].insert(-1,row)
        history=r['final_state']['action_history'];last=history[-1]
        self.assertEqual(last['name'],'finish');last['seq']+=1
        history.insert(-1,{'seq':row['seq'],'name':row['name'],'input':deepcopy(row['input'])})
        with self.assertRaisesRegex(core.AssessmentInputError,'unserviced-torque-success'):run(r)

    def test_declared_attempt_cap_accepts_1024_and_refuses_1025(self):
        r=base();last=r['final_state_sha256']
        for seq in range(len(r['actions'])+1,1025):
            r['actions'].append({'seq':seq,'name':'look','input':{},'result':{'ok':False,'error':'Authored later refusal'},
                                 'pre_state_sha256':last,'post_state_sha256':last})
        value=run(r)
        self.assertEqual(value['tool_calls'],{'attempted':1024,'successful':187,'refused':837})
        self.assertEqual(value['limits']['action_attempts'],1024)
        r['actions'].append(deepcopy(r['actions'][-1]));r['actions'][-1]['seq']=1025
        with self.assertRaisesRegex(core.AssessmentInputError,'record-domain'):run(r)

    def test_supply_roles_and_new_wrong_work_base(self):
        for role,want in [('head_supply','head'),('timing_belt_supply','timing_belt'),('head_bolt','head_bolt')]:
            self.assertEqual(core.effective_role({'role':role}),want)
        policy=deepcopy(base()['config']['repair_scoring']['human_time_policy'])
        policy['base_classification']=core.CLASSIFICATION
        for label in ('wrong_part','wrong_service_decision'):
            policy['mistakes'][label]={'seconds':20,'source_ids':policy['unknown_action']['source_ids']}
            value=core.time_charge(policy,'look',True,[label])
            self.assertEqual(value['productive_seconds'],0)
            self.assertEqual(value['penalty_seconds'],30)

if __name__=='__main__':unittest.main()
