"""Explicit source free-length transport, synthetic SI/measurement fixtures only."""
import copy
import unittest
from hgj.codec import digest
from hgj.game import Game,replay
from hgj.action_conditions import apply_effects
from tests import test_initial_conditions as initial_controls

class BoltLengthTransportTests(unittest.TestCase):
    def config(self,value='absent'):
        c=initial_controls.InitialConditionsTests().config()
        for p in c['geometry']['parts']:
            if p['id']=='cover':p['installed']=False
        packet=c['initial_conditions'];packet['values']['parts']['cover']['location']='supply'
        packet['geometry_sha256']=digest(c['geometry'])
        if value!='absent':
            packet['values']['bolts']['hb03']['free_length_mm']=value
            packet['field_sources']['/bolts/hb03/free_length_mm']={'sha256':'a'*64,'status':'unknown' if value is None else 'estimated',
                'note':'Synthetic free-length datum for transport only, not selected hardware'}
        return c

    def removed(self,c):
        game=Game(c)
        self.assertTrue(game.call('remove',{'part_id':'belt'})['ok'])
        self.assertTrue(game.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
        self.assertTrue(game.call('remove',{'part_id':'hb03'})['ok']);return game

    def test_explicit_free_length_is_sourced_measured_and_preserved_by_replay(self):
        c=self.config(61.8);game=self.removed(c)
        result=game.call('measure',{'target':'hb03','kind':'bolt_free_length'});self.assertTrue(result['ok'],result)
        self.assertEqual(result['observation']['value'],61.8);self.assertEqual(result['observation']['unit'],'mm')
        self.assertEqual(replay(game.export()),game.export())
        del c['initial_conditions']['field_sources']['/bolts/hb03/free_length_mm']
        with self.assertRaises(ValueError):Game(c)
        for value in (0,-1,True,'61.8',float('nan')):
            with self.subTest(value=value),self.assertRaises(ValueError):Game(self.config(value))

    def test_unknown_or_omitted_free_length_is_not_inferred_from_threads_or_stretch(self):
        for value in ('absent',None):
            c=self.config(value);game=self.removed(c)
            result=game.call('measure',{'target':'hb03','kind':'bolt_free_length'});self.assertTrue(result['ok'],result)
            self.assertIsNone(result['observation']['value'])
            self.assertEqual(replay(game.export()),game.export())
        c=self.config(61.8);c['factors']['feedback']=False;game=self.removed(c)
        result=game.call('measure',{'target':'hb03','kind':'bolt_free_length'})
        self.assertEqual(result['observation'],{'feedback':'disabled'})

    def test_removed_supply_measurement_and_replacement_do_not_copy_old_body_length(self):
        c=self.config(61.8)
        packet=c['initial_conditions'];packet['values']['bolts']['new_hb03']['free_length_mm']=61.2
        packet['field_sources']['/bolts/new_hb03/free_length_mm']={'sha256':'b'*64,'status':'estimated',
            'note':'Synthetic distinct supply length, no hardware specification'}
        game=Game(c)
        self.assertFalse(game.call('measure',{'target':'hb03','kind':'bolt_free_length'})['ok'])
        self.assertEqual(game.call('measure',{'target':'new_hb03','kind':'bolt_free_length'})['observation']['value'],61.2)
        self.assertTrue(game.call('remove',{'part_id':'belt'})['ok'])
        self.assertTrue(game.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
        self.assertTrue(game.call('remove',{'part_id':'hb03'})['ok'])
        self.assertTrue(game.call('replace',{'part_id':'hb03','replacement_id':'new_hb03'})['ok'])
        self.assertEqual(game.state['bolts']['hb03']['free_length_mm'],61.8)
        self.assertEqual(game.state['bolts']['new_hb03']['free_length_mm'],61.2)
        self.assertEqual(game.state['condition_sources']['/bolts/new_hb03/free_length_mm']['sha256'],'b'*64)
        self.assertEqual(replay(game.export()),game.export())

    def test_length_effect_is_positive_or_unknown_and_stretch_effect_cannot_leave_stale_length(self):
        before={'parts':{},'bolts':{'b':{'stretch_mm':0.1,'free_length_mm':61.8}},'surfaces':{},'gasket':{},'timing':{}}
        op={'before_conditions':copy.deepcopy(before),'before_conditions_sha256':digest(before)}
        def packet(fields):return {'schema':'hgj/action-conditions/v1','operation_sha256':digest(op),
            'before_conditions_sha256':digest(before),'fields':{p:{'value':v,'source_sha256':'a'*64,
                'status':'unknown' if v is None else 'estimated','note':'Synthetic length transport only'} for p,v in fields.items()}}
        paths={'/bolts/b/stretch_mm','/bolts/b/free_length_mm'}
        updated=apply_effects(before,op,packet({'/bolts/b/stretch_mm':0.2,'/bolts/b/free_length_mm':61.9}),
            required_paths=paths,allowed_paths=paths,source_pins={'a'*64})
        self.assertEqual(updated['bolts']['b']['free_length_mm'],61.9);self.assertEqual(before['bolts']['b']['free_length_mm'],61.8)
        unknown=apply_effects(before,op,packet({'/bolts/b/free_length_mm':None}),
            required_paths={'/bolts/b/free_length_mm'},allowed_paths=paths,source_pins={'a'*64})
        self.assertIsNone(unknown['bolts']['b']['free_length_mm'])
        with self.assertRaisesRegex(ValueError,'free.length|length.*stretch'):
            apply_effects(before,op,packet({'/bolts/b/stretch_mm':0.2}),required_paths={'/bolts/b/stretch_mm'},allowed_paths=paths,source_pins={'a'*64})
        for value in (0,-1,True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                apply_effects(before,op,packet({'/bolts/b/free_length_mm':value}),required_paths={'/bolts/b/free_length_mm'},allowed_paths=paths,source_pins={'a'*64})
