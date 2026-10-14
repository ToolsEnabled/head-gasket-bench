"""Authored inspection/sealant/carried-refit observations, not repair runs."""
from copy import deepcopy
import unittest
from job_accuracy.checkpoint_contracts import original_cover_evidence


def example():
    c={'variant_id':'V1','policy':{},'geometry':{'parts':[
        {'id':'cover','role':'valve_cover','installed':True},
        {'id':'old','role':'cover_gasket_old','installed':True},
        {'id':'new','role':'cover_gasket_new','installed':False}]}}
    f={'parts':{'cover':{'location':'assembly','damaged':False},'old':{'location':'assembly','damaged':False},
                'new':{'location':'supply','damaged':False}},'surfaces':{'cover_face':{'cam_holder_corner_sealant':True}}}
    a=[{'seq':1,'name':'remove','input':{'part_id':'cover'},'result':{'ok':True,'carried_body_ids':['old']}},
       {'seq':2,'name':'inspect','input':{'target':'old'},'result':{'ok':True,'observation':{'damaged':False}}},
       {'seq':3,'name':'clean','input':{'target':'cover_face','sealant':'cam_holder_corners'},'result':{'ok':True}},
       {'seq':4,'name':'install','input':{'part_id':'cover'},'result':{'ok':True,'carried_body_ids':['old']}}]
    return c,f,a


def negative_values():
    values=[]
    for key in original_cover_evidence(*example())['requirements']:
        c,f,a=example()
        if key=='one_original_installed':f['parts']['old']['location']='tray'
        elif key=='no_replacement_cover_also_installed':f['parts']['new']['location']='assembly'
        elif key=='original_condition_observed_serviceable':f['parts']['old']['damaged']=None
        elif key=='inspection_before_refit':
            late=deepcopy(a[1]);late['seq']=5;a.append(late);a[1]['result']['observation']={}
        elif key=='latest_inspection_serviceable':
            late=deepcopy(a[1]);late['seq']=5;late['result']['observation']['damaged']=True;a.append(late)
        elif key=='current_refit_observed':a[0]['result']['carried_body_ids']=[]
        elif key=='sealant_before_refit':a[2]['input']['sealant']='none'
        else:f['surfaces']['cover_face']['cam_holder_corner_sealant']=None
        values.append((key,(c,f,a)))
    return values


class AmendedCover(unittest.TestCase):
    def test_carried_original_has_explicit_inspection_sealant_and_refit(self):
        value=original_cover_evidence(*example())
        self.assertTrue(all(value['requirements'].values()));self.assertEqual(value['refit_sequence'],4)
        self.assertEqual(value['evidence_sequences'],[1,2,3,4])

    def test_every_requirement_has_a_distinct_missing_witness(self):
        for key,args in negative_values():
            with self.subTest(requirement=key):
                value=original_cover_evidence(*args)
                self.assertEqual([k for k,v in value['requirements'].items() if not v],[key])

    def test_late_or_refused_actions_do_not_supply_pre_refit_work(self):
        for name in ('inspect','clean'):
            c,f,a=example();row=next(r for r in a if r['name']==name);row['seq']=5;a.sort(key=lambda r:r['seq'])
            self.assertFalse(all(original_cover_evidence(c,f,a)['requirements'].values()))
            c,f,a=example();next(r for r in a if r['name']==name)['result']['ok']=False
            self.assertFalse(all(original_cover_evidence(c,f,a)['requirements'].values()))

    def test_later_removal_or_missing_carried_identity_cancels_refit(self):
        c,f,a=example();late=deepcopy(a[0]);late['seq']=5;a.append(late)
        self.assertFalse(original_cover_evidence(c,f,a)['requirements']['current_refit_observed'])
        c,f,a=example();a[-1]['result']['carried_body_ids']=[]
        self.assertFalse(original_cover_evidence(c,f,a)['requirements']['current_refit_observed'])

    def test_boolean_numbers_are_not_condition_or_sealant_observations(self):
        for value in (0,1,None,'false'):
            c,f,a=example();f['parts']['old']['damaged']=value
            self.assertFalse(original_cover_evidence(c,f,a)['requirements']['original_condition_observed_serviceable'])
            c,f,a=example();f['surfaces']['cover_face']['cam_holder_corner_sealant']=value
            self.assertFalse(original_cover_evidence(c,f,a)['requirements']['final_sealant_observed'])

    def test_replacement_or_title_does_not_fabricate_original_reuse(self):
        c,f,a=example();first=original_cover_evidence(c,f,a);c['variant_id']='named-correct'
        self.assertEqual(original_cover_evidence(c,f,a),first)
        f['parts']['old']['location']='waste';f['parts']['new']['location']='assembly'
        self.assertFalse(all(original_cover_evidence(c,f,a)['requirements'].values()))
