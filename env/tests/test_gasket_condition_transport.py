"""Source-defined discrete-condition transport, with synthetic receipts only."""
import copy
import json
import unittest
from pathlib import Path
from hgj.backends import Backend
from hgj.codec import digest,file_digest
from hgj.game import Game,replay
from tests import test_game_condition_effects as effects

class GasketConditionTransportTests(unittest.TestCase):
    def fixture(self,missing_required=False,missing_effect=False):
        helper=effects.GameConditionEffectsTests();self.addCleanup(helper.doCleanups)
        config,backend=helper.fixture();path=Path(backend.descriptor['module'])
        source=effects.SOURCE.replace("elif op['kind']=='install':values={'/timing/cam_phase_deg':12,'/timing/crank_phase_deg':-2}",
            "elif op['kind']=='install':values={'/gasket/orientation':'down','/gasket/condition':'synthetic fresh case'}")
        source=source.replace("else:values={'/parts/belt/damaged':False}",
            "else:values={'/parts/'+op['part_id']+'/damaged':False}")
        if missing_effect:
            source=source.replace("'synthetic fresh case'}","'synthetic fresh case'}\n    if op['kind']=='install':values.pop('/gasket/condition')")
        path.write_text(source);descriptor={**backend.descriptor,'sha256':file_digest(path)}
        for p in config['geometry']['parts']:
            if p['id']=='head':p['installed']=False
        initial=config['initial_conditions'];initial['values']['parts']['head']['location']='supply'
        initial['values']['gasket']['condition']='synthetic failed case'
        initial['field_sources']['/gasket/condition']={'sha256':'a'*64,'status':'estimated','note':'Synthetic discrete-case transport only'}
        initial['geometry_sha256']=digest(config['geometry'])
        domain=config['action_domains'];domain.update(geometry_sha256=digest(config['geometry']),
            initial_conditions_sha256=digest(initial),joint_descriptor_sha256=digest(descriptor))
        specs=[('remove',{'part_id':'gasket_old'},['/parts/gasket_old/damaged']),
               ('install',{'part_id':'gasket_new','orientation':'down'},['/gasket/orientation','/gasket/condition'])]
        # Use the actual distinct fixture IDs, never inferred physical stock.
        ids={p['role']:p['id'] for p in config['geometry']['parts'] if p['role'].startswith('gasket_')}
        rules=[]
        for name,args,paths in specs:
            args['part_id']=ids[args['part_id']]
            if name=='remove':paths=['/parts/'+args['part_id']+'/damaged']
            rules.append({'id':'transport-'+name,'tool':name,'arguments':args,'supported':True,
                'required_paths':paths[:1] if missing_required and name=='install' else paths,
                'fields':{p:{'source_pins':[descriptor['sha256']],'statuses':['estimated']} for p in paths},
                'validation_sha256':'e'*64,'reason':'Synthetic gasket-state consumer transport only'})
        domain['rules']=rules;domain_path=path.parent/'transport_domain.json'
        domain_path.write_text(json.dumps(domain,indent=2,ensure_ascii=False))
        config['identity']['action_domains_sha256']=file_digest(domain_path)
        config['admission'].update(geometry_sha256=digest(config['geometry']),initial_conditions_sha256=digest(initial),
            joint_descriptor_sha256=digest(descriptor),action_domains_sha256=file_digest(domain_path),
            action_domains_body_sha256=digest(domain),action_rule_validation_sha256={r['id']:r['validation_sha256'] for r in rules})
        return config,Backend(descriptor,config['admission']),ids

    def test_gasket_condition_survives_structural_install_and_source_effect_replay(self):
        c,j,ids=self.fixture();g=Game(c,joint=j)
        self.assertTrue(g.call('remove',{'part_id':ids['gasket_old']})['ok'])
        result=g.call('install',{'part_id':g.public_id(ids['gasket_new']),'orientation':'down'})
        self.assertTrue(result['ok'],result)
        self.assertEqual(g.state['gasket']['condition'],'synthetic fresh case')
        self.assertEqual(g.state['gasket']['orientation'],'down')
        self.assertEqual(g.state['parts'][ids['gasket_new']]['location'],'assembly')
        self.assertEqual(replay(g.export(),joint=j),g.export())

    def test_new_active_gasket_cannot_inherit_the_old_condition_by_omission(self):
        c,j,ids=self.fixture(missing_required=True);g=Game(c,joint=j)
        self.assertTrue(g.call('remove',{'part_id':ids['gasket_old']})['ok']);before=copy.deepcopy(g.state)
        result=g.call('install',{'part_id':g.public_id(ids['gasket_new']),'orientation':'down'})
        self.assertFalse(result['ok'],result);self.assertEqual(g.state,before)
        self.assertEqual(replay(g.export(),joint=j),g.export())

    def test_fixture_refit_cannot_relabel_the_old_source_condition(self):
        c,j,ids=self.fixture();c.pop('admission');c.pop('action_domains');c['identity']={}
        game=Game(c)
        self.assertTrue(game.call('remove',{'part_id':ids['gasket_old']})['ok']);before=copy.deepcopy(game.state)
        result=game.call('install',{'part_id':game.public_id(ids['gasket_new']),'orientation':'down'})
        self.assertFalse(result['ok'],result);self.assertEqual(game.state,before)
        self.assertEqual(replay(game.export()),game.export())

    def test_missing_source_effect_after_tentative_install_rolls_back_provenance_and_bodies(self):
        c,j,ids=self.fixture(missing_effect=True);game=Game(c,joint=j)
        self.assertTrue(game.call('remove',{'part_id':ids['gasket_old']})['ok']);before=copy.deepcopy(game.state)
        result=game.call('install',{'part_id':game.public_id(ids['gasket_new']),'orientation':'down'})
        self.assertFalse(result['ok'],result);self.assertEqual(game.state,before)
        self.assertIn('Missing required source-defined condition effect',result['refusal'])
        self.assertEqual(game.records[-1]['post_state_sha256'],digest(before))
        self.assertEqual(game.state['condition_sources'],before['condition_sources'])
        self.assertEqual(replay(game.export(),joint=j),game.export())
