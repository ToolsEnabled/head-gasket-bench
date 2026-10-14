"""Authored amendment values; no environment trajectory is claimed."""
from copy import deepcopy
import unittest
from job_accuracy import checkpoints as cp
from job_accuracy import independent as core
from job_accuracy.checkpoint_contracts import ORIGINAL,AMENDMENT1,loosening_step,cover_service_evidence
from test_amended_cover import example as cover_example
from test_successor_components import benchmark,event
from test_checkpoint_chronology import rechain


def assess(r,revision=AMENDMENT1):
    r=rechain(r);settings=r['config']['repair_scoring']
    return cp.score(r,settings['reference'],settings['human_time_policy'],checkpoint_revision=revision,terminal_reason='authored_amendment_value')


def retime(r):
    rechain(r)
    for field,name in [('installed_seq','install'),('tensioned_seq','tension_belt')]:
        r['final_state']['timing'][field]=max(a['seq'] for a in r['actions'] if a['name']==name and a['input'].get('part_id')=='belt')
    return rechain(r)


def diagram(r):
    rows=[a for a in r['actions'] if a['name']=='torque' and a['input'].get('mode')=='loosen' and a['input'].get('part_id','').startswith('hb')]
    for start in range(0,30,10):
        group=deepcopy(rows[start:start+10])
        for target,source in zip(rows[start:start+10],[group[i] for i in (0,1,2,3,4,7,6,5,8,9)]):target['input']=source['input']
    return rechain(r)


def reuse(r):
    c=r['config'];f=r['final_state'];a=r['actions'];parts=c['geometry']['parts']
    old=next(p['id'] for p in parts if p['role']=='cover_gasket_old')
    new=next(p['id'] for p in parts if p['role']=='cover_gasket_new')
    cover=next(p['id'] for p in parts if p['role']=='valve_cover')
    # Carried-body receipts are authored to exercise source-independent grading.
    a[:]=[x for x in a if not(x['name']=='remove' and x['input'].get('part_id')==old)
          and not(x['name']=='install' and x['input'].get('part_id')==new)]
    for row in a:
        if row['name'] in ('remove','install') and row['input'].get('part_id')==cover:row['result']['carried_body_ids']=[old]
    idx=next(i for i,row in enumerate(a) if row['name']=='clean' and row['input'].get('target')=='cover_face')
    a.insert(idx,event('inspect',{'target':old},{'damaged':False}))
    f['parts'][old].update(location='assembly',damaged=False);f['parts'][new]['location']='supply'
    return retime(r)


def checkpoint(v,ident):return next(r for r in v['primary_score']['checkpoints'] if r['id']==ident)


class AmendmentIntegration(unittest.TestCase):
    def test_default_remains_original_and_rule_is_explicit(self):
        r=benchmark();s=r['config']['repair_scoring']
        implicit=cp.score(r,s['reference'],s['human_time_policy'],terminal_reason='authored_amendment_value')
        self.assertEqual(core.encoded(implicit),core.encoded(assess(r,ORIGINAL)))
        for revision in (None,True,'latest'):
            with self.assertRaisesRegex(core.AssessmentInputError,'checkpoint-rule-version'):assess(r,revision)

    def test_both_new_gaskets_still_pass_under_both_rules(self):
        for revision in (ORIGINAL,AMENDMENT1):
            value=assess(benchmark(),revision);self.assertEqual(value['primary_score']['points_earned'],18)

    def test_diagram_order_has_credit_and_no_wrong_order_penalty(self):
        r=diagram(benchmark());old=assess(deepcopy(r),ORIGINAL);new=assess(r)
        self.assertFalse(checkpoint(old,'CP04')['passed']);self.assertTrue(checkpoint(new,'CP04')['passed'])
        self.assertGreater(old['mistakes']['by_type'].get('wrong_order',0),0)
        self.assertEqual(new['mistakes']['by_type'].get('wrong_order',0),0)

    def test_streaming_prefix_and_process_mistakes_remain_separate(self):
        fasteners={f'p{i}':{'sequence_index':i} for i in range(1,11)}
        for seq in ((10,9,8,7,6,3,4,5,2,1),(10,9,8,7,6,5,4,3,2,1)):
            candidates=(0,1)
            for rank,index in enumerate(seq):
                candidates,wrong=loosening_step(candidates,rank,f'p{index}',fasteners);self.assertFalse(wrong)
        candidates,wrong=loosening_step((0,1),0,'p1',fasteners)
        self.assertTrue(wrong);self.assertEqual(candidates,(0,1))
        candidates,wrong=loosening_step(candidates,5,'p3',fasteners)
        self.assertFalse(wrong);self.assertEqual(candidates,(1,))
        _,wrong=loosening_step(candidates,7,'p3',fasteners);self.assertTrue(wrong)

    def test_reuse_is_logical_service_not_literal_discard_and_new_install(self):
        r=reuse(benchmark());old=assess(deepcopy(r),ORIGINAL);new=assess(r)
        self.assertFalse(checkpoint(old,'CP12')['passed']);self.assertTrue(checkpoint(new,'CP12')['passed'])
        self.assertEqual(new['primary_score']['points_earned'],18)
        rows=[x for x in new['checklist_accuracy']['items'] if x['item'].startswith('service/cover-gasket/')]
        self.assertTrue(rows);self.assertTrue(all(x['correct'] for x in rows))

    def test_missing_reuse_inspection_or_sealant_fails_cp12(self):
        for fault in ('inspect','clean','final_sealant','condition','carried_refit'):
            r=reuse(benchmark())
            if fault in ('inspect','clean'):
                row=next(x for x in r['actions'] if x['name']==fault and x['input'].get('target') in ('cover_face','cover_gasket_old'))
                row['name']='look';row['input']={};row['result']={'ok':True}
            elif fault=='final_sealant':r['final_state']['surfaces']['cover_face']['cam_holder_corner_sealant']=False
            elif fault=='condition':r['final_state']['parts']['cover_gasket_old']['damaged']=True
            else:next(x for x in r['actions'] if x['name']=='install' and x['input'].get('part_id')=='cover')['result']['carried_body_ids']=[]
            self.assertFalse(checkpoint(assess(retime(r)),'CP12')['passed'],fault)

    def test_cover_reuse_does_not_waive_head_gasket_or_other_parts(self):
        for body in ('gasket_old','cover'):
            r=reuse(benchmark());r['final_state']['parts'][body]['location']='tray'
            self.assertFalse(checkpoint(assess(r),'CP12')['passed'])

    def test_independent_pass_choices_and_wrong_increment(self):
        r=diagram(benchmark());rows=[x for x in r['actions'] if x['name']=='torque' and x['input'].get('mode')=='loosen' and x['input'].get('part_id','').startswith('hb')]
        for i,body in enumerate(range(10,0,-1)):rows[10+i]['input']['part_id']=f'hb{body:02}'
        value=assess(r);self.assertTrue(checkpoint(value,'CP04')['passed'])
        self.assertEqual(value['mistakes']['by_type'].get('wrong_order',0),0)
        r=diagram(benchmark());next(x for x in r['actions'] if x['name']=='torque' and x['input'].get('part_id')=='hb10')['input']['angle_deg']=-60
        self.assertFalse(checkpoint(assess(r),'CP04')['passed'])

    def test_primary_rejects_secondary_from_different_rule(self):
        r=benchmark();value=assess(r,ORIGINAL)
        with self.assertRaisesRegex(core.AssessmentInputError,'checkpoint-secondary-version'):
            cp.evaluate(r,r['config']['repair_scoring']['reference'],value,checkpoint_revision=AMENDMENT1)

    def test_each_cover_service_condition_reports_its_missing_witness(self):
        for key in ('one_service_position','one_installed_cover_gasket','permitted_cover_service',
                    'replaced_original_discarded','replacement_install_observed'):
            c,f,a=cover_example()
            if key=='one_service_position':c['geometry']['parts'][1]['installed']=False
            elif key=='one_installed_cover_gasket':f['parts']['new']['location']='assembly'
            elif key=='permitted_cover_service':a[1]['result']['observation']['damaged']=True
            else:
                f['parts']['old']['location']='waste';f['parts']['new']['location']='assembly'
                if key=='replaced_original_discarded':f['parts']['old']['location']='tray'
                else:a[-1]['input']['part_id']='cover'
            self.assertFalse(cover_service_evidence(c,f,a)['requirements'][key],key)

    def test_cover_alternative_does_not_depend_on_reference_route(self):
        r=benchmark();ref=r['config']['repair_scoring']['reference']
        ref['final']['parts']['cover_gasket_old']['location']='assembly'
        ref['final']['parts']['cover_gasket_new']['location']='supply'
        ref['actions']=[a for a in ref['actions'] if not(a['name']=='remove' and a['input'].get('part_id')=='cover_gasket_old')
                        and not(a['name']=='install' and a['input'].get('part_id')=='cover_gasket_new')]
        self.assertTrue(checkpoint(assess(r),'CP12')['passed'])

    def test_head_gasket_active_identity_is_still_required(self):
        r=reuse(benchmark());r['final_state']['gasket']['active_id']='gasket_old'
        self.assertFalse(checkpoint(assess(r),'CP12')['passed'])

if __name__=='__main__':unittest.main()
