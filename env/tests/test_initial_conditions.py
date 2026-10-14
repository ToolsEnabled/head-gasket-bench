import copy
import unittest
from hgj.codec import digest
from hgj.fixtures import fixture_config,FixtureJoint
from hgj.game import Game,replay


class InitialConditionsTests(unittest.TestCase):
    def test_optional_gasket_condition_requires_source_and_preserves_unknown(self):
        for condition,status in (('source-defined discrete failed case','estimated'),(None,'unknown')):
            with self.subTest(condition=condition):
                c=self.config();packet=c['initial_conditions'];packet['values']['gasket']['condition']=condition
                packet['field_sources']['/gasket/condition']={'sha256':'a'*64,'status':status,
                    'note':'Synthetic optional condition transport, no gasket law'}
                game=Game(c);self.assertEqual(game.state['gasket']['condition'],condition)
                self.assertEqual(replay(game.export()),game.export())
                del packet['field_sources']['/gasket/condition']
                with self.assertRaises(ValueError):Game(c)

    def test_optional_gasket_condition_is_not_an_untyped_state_injection(self):
        for condition in ('',{},1,True):
            with self.subTest(condition=condition):
                c=self.config();packet=c['initial_conditions'];packet['values']['gasket']['condition']=condition
                # Provenance is a valid scalar entry for scalar cases. Container
                # cases still must refuse rather than accepting opaque metadata.
                packet['field_sources']['/gasket/condition']={'sha256':'a'*64,'status':'estimated','note':'Synthetic invalid transport'}
                with self.assertRaises(ValueError):Game(c)

    def config(self):
        c=fixture_config();g=Game(c)
        values={key:copy.deepcopy(g.state[key]) for key in ('parts','bolts','surfaces','gasket','timing')}
        for f in c['geometry']['fasteners']:
            values['bolts'][f['id']]['install_engagement_turns']=3.5
        for p in c['geometry']['parts']:
            if p['role']=='head_bolt' and p['id'] not in values['bolts']:
                values['bolts'][p['id']]={'turns':0,'torque_N_m':0,'thread_clean':True,'thread_oiled':False,
                    'washer_oiled':False,'stretch_mm':0.03,'install_engagement_turns':4,'history':[]}
        values['surfaces']['block_deck']['warpage_m']=0.000043
        values['timing']['cam_phase_deg']=7
        sources={}
        def visit(v,path):
            if isinstance(v,dict):
                for k,x in v.items():visit(x,path+'/'+k)
            elif isinstance(v,list):
                for i,x in enumerate(v):visit(x,path+'/'+str(i))
            else:sources[path]={'sha256':'a'*64,'status':'estimated','note':'Offline transport fixture only'}
        visit(values,'')
        c['initial_conditions']={'schema':'hgj/initial-conditions/v1','qualification':'source-defined',
             'geometry_sha256':digest(c['geometry']),'variant_sha256':digest(c['variants'][0]),
             'values':values,'field_sources':sources}
        return c

    def test_explicit_values_and_supply_condition_survive_actions_and_replay(self):
        c=self.config();g=Game(c)
        self.assertEqual(g.state['surfaces']['block_deck']['warpage_m'],0.000043)
        self.assertEqual(g.state['timing']['cam_phase_deg'],7)
        for action,args in [('look',{}),('remove',{'part_id':'belt'})]:self.assertTrue(g.call(action,args)['ok'])
        self.assertEqual(replay(g.export()),g.export())

    def test_physical_configuration_missing_initial_conditions_refuses_before_joint(self):
        c=fixture_config();c['admission']={'status':'validated-physics'}
        class MustNotInitialize:
            def initialize(self,config):raise AssertionError('Initialization reached before required input validation')
        with self.assertRaisesRegex(ValueError,'initial conditions'):Game(c,joint=MustNotInitialize())

    def test_missing_source_wrong_identity_or_nonfinite_value_refuses(self):
        for kind in ('source','geometry','variant','nonfinite','missing_part'):
            c=self.config();packet=c['initial_conditions']
            if kind=='source':del packet['field_sources']['/timing/cam_phase_deg']
            elif kind in ('geometry','variant'):packet[kind+'_sha256']='b'*64
            elif kind=='nonfinite':packet['values']['bolts']['hb01']['stretch_mm']=float('nan')
            else:del packet['values']['parts']['block']
            with self.subTest(kind=kind),self.assertRaises(ValueError):Game(c)

    def test_refit_uses_declared_engagement_and_replacement_uses_supply_condition(self):
        c=self.config();g=Game(c)
        self.assertTrue(g.call('remove',{'part_id':'belt'})['ok'])
        for f in c['geometry']['fasteners']:
            if f['group']=='cover':
                self.assertTrue(g.call('torque',{'part_id':f['id'],'mode':'loosen','angle_deg':-360})['ok'])
                self.assertTrue(g.call('remove',{'part_id':f['id']})['ok'])
                self.assertTrue(g.call('remove',{'part_id':f['washer_id']})['ok'])
        self.assertTrue(g.call('remove',{'part_id':'cover'})['ok'])
        self.assertTrue(g.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
        self.assertTrue(g.call('remove',{'part_id':'hb03'})['ok'])
        self.assertTrue(g.call('replace',{'part_id':'hb03','replacement_id':'new_hb03'})['ok'])
        self.assertEqual(g.state['bolts']['new_hb03']['stretch_mm'],0.03)
        self.assertTrue(g.state['bolts']['new_hb03']['thread_clean'])
        self.assertTrue(g.call('install',{'part_id':'new_hb03'})['ok'])
        self.assertEqual(g.state['bolts']['new_hb03']['turns'],4)
        self.assertEqual(len(g.state['bolts']['new_hb03']['history']),2)
        self.assertEqual(replay(g.export()),g.export())
