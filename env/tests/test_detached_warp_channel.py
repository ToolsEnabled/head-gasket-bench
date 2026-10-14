"""Two-action diagnostic fixtures; no native law, public repair or physical score."""
import copy
import importlib
import unittest

from hgj.fixtures import fixture_config
from tests import test_source_runtime as runtime_tests
from tools.source_server import SourceRuntime


class DiagnosticJoint:
    """Synthetic numeric loaded span, deliberately separate from residual warp."""
    def __init__(self, qualification='detached-estimate', explicit_basis=True):
        self.qualification=qualification
        self.explicit_basis=explicit_basis

    def initialize(self, config):
        result={'bolt_tensions_N':{f['id']:0 for f in config['geometry']['fasteners']
                                  if f['group']=='head'},
                'head_warpage_m':0.001,'qualification':self.qualification,
                'acceptance_eligible':False}
        if self.explicit_basis:
            result['head_warpage_basis']=(None if self.explicit_basis=='unknown' else
                'Synthetic instantaneous loaded span; not residual surface warp')
        return result

    def apply(self, state, operation):
        return copy.deepcopy(state)


class DetachedWarpChannelTests(unittest.TestCase):
    def run_channel(self, qualification, explicit_basis, initial_warp, feedback=True):
        helper=runtime_tests.SourceRuntimeTests();self.addCleanup(helper.doCleanups)
        root,path,pin,_=helper.snapshot();runtime=SourceRuntime(root,path,pin)
        config=fixture_config()
        config['factors']['feedback']=feedback
        # Software-only mid-service condition: head and its retainers are out;
        # old gasket is the next removable body. No actual initial mechanics.
        for part in config['geometry']['parts']:
            part['installed']=part['id'] in ('block','gasket_old')
        config['variants'][0]['warpage_m']={'head_face':initial_warp}
        with runtime.active():
            module=importlib.import_module('hgj.game')
            joint=DiagnosticJoint(qualification,explicit_basis)
            game=module.Game(config,joint=joint,source_runtime=runtime)
            self.assertTrue(game.call('remove',{'part_id':'gasket_old'})['ok'])
            measured=game.call('measure',{'target':'head_face','kind':'flatness'})
            self.assertTrue(measured['ok'])
            record=game.export()
            self.assertEqual(game.state['joint']['head_warpage_m'],0.001)
            self.assertFalse(game.state['joint']['acceptance_eligible'])
            self.assertIsNone(record['score'])
            self.assertEqual(module.replay(record,joint=joint,source_runtime=runtime),record)
            observation=measured['observation']['value'] if feedback else measured['observation']
            return observation,record['final_state']['surfaces']['head_face']['warpage_m']

    def test_detached_numeric_span_keeps_known_residual_flatness(self):
        for basis in (False,True):
            with self.subTest(explicit_basis=basis):
                observation,surface=self.run_channel('detached-estimate',basis,0.00002)
                self.assertEqual(observation,0.00002)
                self.assertEqual(surface,0.00002)

    def test_detached_numeric_span_keeps_unknown_residual_null(self):
        observation,surface=self.run_channel('detached-estimate',True,None)
        self.assertIsNone(observation)
        self.assertIsNone(surface)

    def test_explicit_loaded_basis_keeps_other_fixture_surface_separate(self):
        observation,surface=self.run_channel('software-fixture',True,0.00002)
        self.assertEqual(observation,0.00002)
        self.assertEqual(surface,0.00002)

    def test_legacy_untyped_fixture_retains_its_previous_warp_semantics(self):
        observation,surface=self.run_channel('software-fixture',False,0.00002)
        self.assertEqual(observation,0.001)
        self.assertEqual(surface,0.001)

    def test_explicit_unknown_basis_keeps_surface_unknown(self):
        observation,surface=self.run_channel('software-fixture','unknown',None)
        self.assertIsNone(observation)
        self.assertIsNone(surface)

    def test_disabled_feedback_keeps_the_same_residual_mechanics(self):
        value,surface_on=self.run_channel('detached-estimate',True,0.00002)
        observation,surface_off=self.run_channel('detached-estimate',True,0.00002,feedback=False)
        self.assertEqual(value,0.00002)
        self.assertEqual(observation,{'feedback':'disabled'})
        self.assertEqual(surface_on,surface_off)
