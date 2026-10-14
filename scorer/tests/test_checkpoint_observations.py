"""Latest timing observations and equivalent numeric commands are behavior."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from job_accuracy import checkpoints
from job_accuracy import report
from job_accuracy.independent import assess
from tools.test_repair_checkpoints import evaluate,commit
from test_checkpoint_chronology import base,rechain,primary


class Observations(unittest.TestCase):
    def test_invalid_boolean_observations_share_unknown_display(self):
        for value in (1,0,'false',[],{}):
            self.assertEqual(report.truth(value),report.truth(None))
        self.assertNotEqual(report.truth(True),report.truth(None))
        self.assertNotEqual(report.truth(False),report.truth(None))

    def test_invalid_numeric_observations_share_unknown_display(self):
        for value in (False,True,float('inf'),float('nan'),'73'):
            self.assertEqual(report.number(value),report.number(None))
        self.assertNotEqual(report.number(0),report.number(None))

    def test_later_negative_before_removal_cancels_earlier_positive(self):
        r=base();r['actions'][1].update(name='check_timing',input={'crank_revolutions':2},result={'ok':True,'observation':{'tdc_cylinder':1,'marks_align':False}})
        self.assertFalse(primary(r,'CP03'))

    def test_latest_post_install_negative_prevents_timing_credit(self):
        r=base();row=max((x for x in r['actions'] if x['name']=='check_timing'),key=lambda x:x['seq'])
        row['result']['observation']['marks_align']=False
        self.assertFalse(primary(r,'CP11'))

    def test_equivalent_integer_float_angles_preserve_credit(self):
        r=base()
        for row in r['actions']:
            if row['name']=='torque' and row['input'].get('mode')=='loosen':row['input']['angle_deg']=float(row['input']['angle_deg'])
        self.assertTrue(primary(r,'CP04'))

    def test_angle_changes_and_boolean_numbers_do_not_match(self):
        expected=[{'part_id':'a','mode':'loosen','angle_deg':-120}]
        for value in (True,-60,None,float('inf')):
            actual=deepcopy(expected);actual[0]['angle_deg']=value
            self.assertFalse(checkpoints.same_loosening(actual,expected))
        changed=deepcopy(expected);changed[0]['part_id']='b'
        self.assertFalse(checkpoints.same_loosening(changed,expected))

    def test_final_observations_remain_separate_from_commands(self):
        r=base();r['final_state']['bolts']['hb01']['torque_N_m']=None;result=evaluate(commit(r))
        bolt=next(x for x in result['bolt_accuracy']['bolts'] if x['body_id']=='hb01')
        self.assertEqual(bolt['stages'][1]['value_N_m'],73)
        self.assertIsNone(bolt['final_observations']['torque_N_m'])
        self.assertEqual(bolt['final_observations']['stretch_mm'],0)
        self.assertIs(bolt['final_observations']['damaged'],False)
        self.assertIsNone(bolt['checks']['final_stage_value'])


if __name__=='__main__':unittest.main()
