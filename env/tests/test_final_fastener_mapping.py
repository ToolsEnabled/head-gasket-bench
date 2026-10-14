"""Private v2 structural position transport; no model/native/subject job."""
import copy
import importlib
import json
import unittest
from hgj.codec import digest
from hgj.fixtures import fixture_config
from tests import test_source_runtime as source_controls

class FinalFastenerMappingTests(unittest.TestCase):
    def runtime(self):
        helper=source_controls.SourceRuntimeTests();self.addCleanup(helper.doCleanups)
        root,path,pin,manifest=helper.snapshot();return source_controls.SourceRuntime(root,path,pin)

    def release_bolt(self,game,config):
        for name,args in [('remove',{'part_id':'belt'})]:self.assertTrue(game.call(name,args)['ok'])
        for f in config['geometry']['fasteners']:
            if f['group']=='cover':
                for name,args in [('torque',{'part_id':f['id'],'mode':'loosen','angle_deg':-360}),
                                  ('remove',{'part_id':f['id']}),('remove',{'part_id':f['washer_id']})]:
                    self.assertTrue(game.call(name,args)['ok'])
        self.assertTrue(game.call('remove',{'part_id':'cover'})['ok'])
        self.assertTrue(game.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
        self.assertTrue(game.call('remove',{'part_id':'hb03'})['ok'])

    def test_selected_replacement_position_is_private_hashed_and_replays(self):
        runtime=self.runtime()
        with runtime.active():
            module=importlib.import_module('hgj.game');config=fixture_config();game=module.Game(config,source_runtime=runtime)
            self.assertEqual(game.state['fastener_mapping'],game._position_map())
            self.release_bolt(game,config)
            original=copy.deepcopy(game.fasteners['hb03'])
            result=game.call('replace',{'part_id':'hb03','replacement_id':'new_hb03'});self.assertTrue(result['ok'],result)
            mapping=game.state['fastener_mapping'];expected={'body_id':'new_hb03','service_position_id':'hb03',
                'group':original['group'],'sequence_index':original['sequence_index'],'washer_id':original['washer_id'],
                'holds':original['holds'],'service_required':original.get('service_required',True),
                'spec_ref':original.get('spec_ref'),'position_source_id':original['source_id']}
            self.assertEqual(mapping['new_hb03'],expected);self.assertNotIn('hb03',mapping);self.assertNotIn('thread',mapping['new_hb03'])
            self.assertEqual(game.state['identity']['fastener_mapping_sha256'],digest(mapping))
            self.assertEqual(game.state['parts']['hb03']['location'],'waste')
            self.assertEqual(game.state['parts']['new_hb03']['location'],'tray')
            self.assertNotIn('fastener_mapping',json.dumps(result))
            self.assertNotIn('fastener_mapping',json.dumps(game.call('look',{})))
            self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())
            before=copy.deepcopy(game.state)
            refused=game.call('replace',{'part_id':'new_hb03','replacement_id':'gasket_good'})
            self.assertFalse(refused['ok']);self.assertEqual(game.state,before)
            self.assertEqual(module.replay(game.export(),source_runtime=runtime),game.export())

    def test_soak_receives_same_mapping_and_legacy_does_not_acquire_v2_claim(self):
        runtime=self.runtime();seen=[]
        class Joint:
            def initialize(self,config):return {'bolt_tensions_N':{f['id']:0 for f in config['geometry']['fasteners'] if f['group']=='head'},'head_warpage_m':0}
        class Sink:
            def score(self,job):
                seen.append(copy.deepcopy(job))
                return {'schema':'hgj/soak-result/v1','status':'UNQUALIFIED','qualification':'unqualified',
                        'pass':None,'time_to_failure_s':None,'cause':'Pure structural forwarding control only'}
        with runtime.active():
            module=importlib.import_module('hgj.game');game=module.Game(fixture_config(),joint=Joint(),soak=Sink(),source_runtime=runtime)
            result=game.call('finish',{});self.assertTrue(result['ok'],result)
            self.assertEqual(seen[0]['fastener_mapping'],game._position_map())
            self.assertEqual(seen[0],game.state)
            self.assertNotIn('fastener_mapping',json.dumps(result))
            legacy=module.Game(fixture_config());self.assertNotIn('fastener_mapping',legacy.state)
            self.assertNotIn('fastener_mapping_sha256',legacy.state['identity'])
            self.assertEqual(legacy.export()['schema'],'hgj/run/v1')
