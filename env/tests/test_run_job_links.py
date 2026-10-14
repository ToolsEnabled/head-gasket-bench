"""Private v2 config/selected-variant/source joins; pure source fixtures only."""
import copy
import importlib
import json
import unittest
from hgj.codec import digest
from hgj.fixtures import fixture_config
from tests import test_source_runtime as source_controls

class RunJobLinkTests(unittest.TestCase):
    def runtime(self):
        helper=source_controls.SourceRuntimeTests();self.addCleanup(helper.doCleanups)
        root,path,pin,manifest=helper.snapshot();return source_controls.SourceRuntime(root,path,pin)

    def test_v2_job_binds_actual_config_selected_variant_and_source_without_public_leak(self):
        runtime=self.runtime();c=fixture_config()
        with runtime.active():
            module=importlib.import_module('hgj.game');game=module.Game(c,source_runtime=runtime)
            variant=next(v for v in c['variants'] if v['id']==c['variant_id'])
            self.assertEqual(game.state['identity']['selected_variant_sha256'],digest(variant))
            self.assertEqual(game.state['identity']['environment_source_sha256'],digest(runtime.identity))
            self.assertEqual(game.state['identity']['config_sha256'],game.export()['config_sha256'])
            self.assertTrue(game.call('look',{})['ok']);self.assertTrue(game.call('finish',{})['ok'])
            self.assertNotIn('selected_variant_sha256',json.dumps(game.records[-1]['result']))
            self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())
            legacy=module.Game(c);self.assertNotIn('selected_variant_sha256',legacy.state['identity'])
            self.assertNotIn('environment_source_sha256',legacy.state['identity'])

    def test_config_identity_cannot_overwrite_owned_v2_body_commitments(self):
        runtime=self.runtime();c=fixture_config();c['identity']={'config_sha256':'f'*64,
            'selected_variant_sha256':'e'*64,'environment_source_sha256':'d'*64}
        with runtime.active():
            module=importlib.import_module('hgj.game');game=module.Game(c,source_runtime=runtime)
            self.assertEqual(game.state['identity']['config_sha256'],digest(c))
            self.assertEqual(game.state['identity']['selected_variant_sha256'],digest(game.variant))
            self.assertEqual(game.state['identity']['environment_source_sha256'],game.export()['environment_source_sha256'])
            self.assertEqual(c['identity']['config_sha256'],'f'*64)
            self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())
