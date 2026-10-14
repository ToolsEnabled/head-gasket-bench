"""Source-v2 export rejects inconsistent private commitments without mutation."""
import copy
import importlib
import unittest
from hgj.codec import digest
from hgj.fixtures import fixture_config
from tests import test_source_runtime as source_controls


class ExportOwnedCommitmentTests(unittest.TestCase):
    def runtime(self):
        helper=source_controls.SourceRuntimeTests();self.addCleanup(helper.doCleanups)
        root,path,pin,manifest=helper.snapshot();return source_controls.SourceRuntime(root,path,pin)

    def refuses_without_mutation(self,game):
        state=copy.deepcopy(game.state);records=copy.deepcopy(game.records)
        with self.assertRaises(ValueError):game.export()
        self.assertEqual(game.state,state);self.assertEqual(game.records,records)

    def test_export_refuses_each_stale_owned_identity_commitment(self):
        runtime=self.runtime()
        with runtime.active():
            module=importlib.import_module('hgj.game')
            for field in ('config_sha256','selected_variant_sha256','environment_source_sha256',
                          'fastener_mapping_sha256','joint_state_sha256','action_history_sha256'):
                with self.subTest(field=field):
                    game=module.Game(fixture_config(),source_runtime=runtime)
                    self.assertTrue(game.call('look',{})['ok']);original=copy.deepcopy(game.state['identity'])
                    game.state['identity'][field]='f'*64;self.refuses_without_mutation(game)
                    game.state['identity']=original
                    self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())

    def test_export_refuses_rehashed_mapping_changed_config_variant_or_selected_id(self):
        runtime=self.runtime()
        with runtime.active():
            module=importlib.import_module('hgj.game')
            for case in ('mapping','config','variant','selected_id'):
                with self.subTest(case=case):
                    game=module.Game(fixture_config(),source_runtime=runtime)
                    if case=='mapping':
                        game.state['fastener_mapping']['hb03']['service_position_id']='forged'
                        game.state['identity']['fastener_mapping_sha256']=digest(game.state['fastener_mapping'])
                    elif case=='config':game.config['factors']['feedback']=not game.config['factors']['feedback']
                    elif case=='variant':
                        game.variant=copy.deepcopy(game.variant);game.variant['substituted']=True
                        game.state['identity']['selected_variant_sha256']=digest(game.variant)
                    else:game.state['variant_id']='forged'
                    self.refuses_without_mutation(game)
