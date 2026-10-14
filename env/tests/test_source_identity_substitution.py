"""Post-construction source claims require actual active owner, never data alone."""
import copy
import importlib
import unittest
from hgj.game import Game
from hgj.fixtures import fixture_config
from tests import test_source_runtime as source_controls

class SourceIdentitySubstitutionTests(unittest.TestCase):
    def runtime(self):
        helper=source_controls.SourceRuntimeTests();self.addCleanup(helper.doCleanups)
        root,path,pin,manifest=helper.snapshot();return source_controls.SourceRuntime(root,path,pin)

    def test_legacy_instance_cannot_acquire_source_custody_by_attribute_assignment(self):
        runtime=self.runtime();game=Game(fixture_config());game.environment_source=runtime.identity
        state=copy.deepcopy(game.state);records=copy.deepcopy(game.records);budget=game.budget()
        with self.assertRaises(ValueError):game.export()
        with self.assertRaises(ValueError):game.call('look',{})
        self.assertEqual(game.state,state);self.assertEqual(game.records,records)
        self.assertEqual(game.budget(),budget);self.assertFalse(game.finished);self.assertIsNone(game.score)

    def test_active_instance_rejects_identity_substitution_and_accepts_only_its_owned_body(self):
        runtime=self.runtime()
        with runtime.active():
            module=importlib.import_module('hgj.game');game=module.Game(fixture_config(),source_runtime=runtime)
            actual=copy.deepcopy(game.environment_source)
            game.environment_source['manifest_body_sha256']='f'*64
            state=copy.deepcopy(game.state);records=copy.deepcopy(game.records);budget=game.budget()
            with self.assertRaises(ValueError):game.export()
            with self.assertRaises(ValueError):game.call('look',{})
            self.assertEqual(game.state,state);self.assertEqual(game.records,records)
            self.assertEqual(game.budget(),budget);self.assertFalse(game.finished);self.assertIsNone(game.score)
            game.environment_source=actual
            self.assertTrue(game.call('look',{})['ok'])
            self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())
