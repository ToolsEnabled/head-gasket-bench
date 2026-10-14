"""Actual manifest-reader plumbing with synthetic source packets only."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from hgj.backends import load_manifest
from hgj.codec import canonical,digest,file_digest
from hgj.game import Game,replay
from tests.test_game_condition_effects import GameConditionEffectsTests

class ManifestActionPreflightTests(unittest.TestCase):
    def fixture(self,mutation=None):
        fixtures=GameConditionEffectsTests();self.addCleanup(fixtures.doCleanups)
        c,j=fixtures.fixture();root=Path(j.descriptor['module']).parent
        joint=copy.deepcopy(j.descriptor);soak={**joint,'kind':'soak'}
        c['admission']['soak_descriptor_sha256']=digest(soak)
        if mutation=='body':c['action_domains']['rules'][0]['reason']='Post-admission modification'
        elif mutation=='argument':c['action_domains']['rules'][0]['arguments']['unexpected_option']=True
        elif mutation=='source':c['action_domains']['rules'][0]['fields']['/surfaces/cover_face/dry']['source_pins']=['z'*64]
        elif mutation=='initial':c['action_domains']['initial_conditions_sha256']='b'*64
        domain_path=root/'action_domains.json';domain_path.write_text(json.dumps(c['action_domains'],indent=2,ensure_ascii=False))
        c['admission']['action_domains_sha256']=file_digest(domain_path)
        if mutation!='body':c['admission']['action_domains_body_sha256']=digest(c['action_domains'])
        inputs={}
        for name,value in {**{key:c[key] for key in ('geometry','service','labor','variants','policy','initial_conditions','admission')},
                           'joint_descriptor':joint,'soak_descriptor':soak}.items():
            path=root/(name+'.json');path.write_bytes(canonical(value));inputs[name]={'path':path.name,'sha256':file_digest(path)}
        inputs['action_domains']={'path':domain_path.name,'sha256':file_digest(domain_path)}
        manifest={'schema':'hgj/manifest/v1','inputs':inputs,'variant_id':c['variant_id'],'factors':c['factors'],'admission':True}
        path=root/'manifest.json';path.write_bytes(canonical(manifest));return path

    def test_valid_manifest_keeps_raw_and_body_namespaces_and_replays_private_packet(self):
        path=self.fixture();c,j,s=load_manifest(path)
        self.assertNotEqual(c['identity']['action_domains_sha256'],digest(c['action_domains']))
        self.assertEqual(j.admission_sha256,s.admission_sha256)
        game=Game(c,joint=j,soak=s);result=game.call('clean',c['action_domains']['rules'][0]['arguments'])
        self.assertTrue(result['ok'],result)
        effect=game.records[-1]['authorized_condition_effects']
        self.assertEqual(effect['domain_file_sha256'],c['identity']['action_domains_sha256'])
        self.assertEqual(effect['domain_body_sha256'],digest(c['action_domains']))
        self.assertEqual(replay(game.export(),joint=j,soak=s),game.export())

    def test_malformed_private_domains_refuse_before_any_backend_compilation(self):
        for mutation in ('body','argument','source','initial'):
            with self.subTest(mutation=mutation):
                path=self.fixture(mutation)
                with patch('hgj.backends.Backend',side_effect=AssertionError('Backend constructor reached')) as spy:
                    with self.assertRaises(ValueError):load_manifest(path)
                    spy.assert_not_called()
