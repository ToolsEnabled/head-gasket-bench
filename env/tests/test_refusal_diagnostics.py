"""Diagnostic-only authored states; no Game trajectory or backend execution."""
import copy
import unittest
from unittest.mock import patch

from hgj import api, benchmark_geometry
from hgj.game import Game, Refusal


class Fixture(Game):
    def __init__(self):
        roles={'head':'head','old':'gasket_old','cover':'valve_cover',
               'bolt':'head_bolt','stock':'gasket_new','seal':'cover_gasket_new'}
        self.part_defs={pid:{'id':pid,'role':role,'removable':True,
                           'requires_installed':[], 'requires_removed':[],
                           'catalog':{'bore_mm':75,'compressed_thickness_mm':0.762}}
                        for pid,role in roles.items()}
        self.public_ids={pid:'public-'+pid for pid in roles}
        self.public_to_body={value:key for key,value in self.public_ids.items()}
        self.state={'parts':{pid:{'location':'assembly','damaged':False} for pid in roles},
                    'bolts':{'bolt':{'turns':0}},
                    'surfaces':{key:{'warpage_m':0,'roughness_ra_um':1}
                                for key in ('head_face','block_deck','cover_face')},
                    'timing':{'set_seq':None,'checks':[]},
                    'benchmark_removal':{'conditions':{'timing_marks_recorded':False},
                                         'released':{'attachment-a':True},'attachment_history':[]}}
        self.fasteners={'bolt':{'id':'bolt','group':'head'}}
        self.config={'policy':{},'factors':{'feedback':True}}
        self.records=[]; self.procedure_scoring=True
        self._active_action=None; self.state['gasket']={'active_id':None}
        self._releases={'attachment-a':{'basis':[]}}

    def _accessible(self, pid): return True
    def budget(self, attempted=None): return None


class Diagnostics(unittest.TestCase):
    def setUp(self): self.game=Fixture()

    def refusal(self, name, args, *text):
        before=copy.deepcopy(self.game.state)
        with self.assertRaises(Refusal) as caught:
            self.game._dispatch_core(name,args)
        for value in text: self.assertIn(value,str(caught.exception))
        self.assertEqual(self.game.state,before)

    def test_identifier_names_key_and_submitted_id(self):
        for key in ('target','part_id','replacement_id'):
            with self.subTest(key=key), self.assertRaises(Refusal) as caught:
                self.game._resolve_arguments({key:'unknown-submitted-id'})
            self.assertIn(key,str(caught.exception))
            self.assertIn('unknown-submitted-id',str(caught.exception))

    def test_surface_registry_and_resolution(self):
        result=self.game._dispatch_core('look',{})
        self.assertEqual(result['surface_ids'],['block_deck','cover_face','head_face'])
        for name in result['surface_ids']:
            self.assertEqual(self.game._resolve_arguments({'target':name}),{'target':name})

    def test_surface_access_names_surface(self):
        self.refusal('measure',{'target':'head_face','kind':'flatness'},'head_face','access predicate')
        self.refusal('clean',{'target':'cover_face','method':'solvent'},'cover_face','carrier is installed')

    def test_measure_domain_separate_from_identifier(self):
        self.refusal('measure',{'target':'seal','kind':'gasket_bore'},'public-seal','gasket_bore','head-gasket stock')
        self.refusal('measure',{'target':'cover','kind':'bolt_stretch'},'public-cover','bolt_stretch','fastener')
        self.refusal('measure',{'target':'stock','kind':'flatness'},'public-stock','flatness','surface ID')

    def test_measure_removed_fastener_requirement(self):
        self.refusal('measure',{'target':'bolt','kind':'bolt_stretch'},'public-bolt','still installed')

    def test_valid_measurement_domains_unchanged(self):
        self.game.state['parts']['head']['location']='tray'
        self.game.state['parts']['old']['location']='waste'
        self.assertEqual(self.game._dispatch_core('measure',{'target':'head_face','kind':'flatness'})['observation']['value'],0)
        self.assertEqual(self.game._dispatch_core('measure',{'target':'stock','kind':'gasket_bore'})['observation']['value'],75)

    def test_clean_separates_domain_and_location(self):
        self.refusal('clean',{'target':'cover','method':'thread_brush'},'public-cover','neither a surface nor a fastener')
        self.refusal('clean',{'target':'bolt','method':'thread_brush'},'public-bolt','assembly','tray')

    def test_install_location_role_and_carrier(self):
        self.refusal('install',{'part_id':'stock'},'public-stock','assembly','tray or supply')
        self.game.state['parts']['old']['location']='tray'
        self.refusal('install',{'part_id':'old'},'public-old','non-installable old head-gasket role')
        self.game.state['parts']['seal'].update(location='tray',carried_with='cover')
        self.refusal('install',{'part_id':'seal'},'public-seal','public-cover')

    def test_replace_location_and_same_body(self):
        self.refusal('replace',{'part_id':'old','replacement_id':'stock'},'part_id','public-old','assembly')
        self.game.state['parts']['old']['location']='waste'
        self.refusal('replace',{'part_id':'old','replacement_id':'stock'},'replacement_id','public-stock','assembly')
        # Both location predicates cannot hold for one body; this remains refused.
        self.game.state['parts']['stock']['location']='supply'
        self.refusal('replace',{'part_id':'stock','replacement_id':'stock'},'part_id','replacement_id','public-stock','same body')

    def test_disengaged_fastener_identity(self):
        self.refusal('torque',{'part_id':'bolt','mode':'loosen','angle_deg':-120},'public-bolt','disengaged','turns=0')

    def test_replace_names_retained_carrier(self):
        self.game.state['parts']['seal'].update(location='tray',carried_with='cover')
        self.refusal('replace',{'part_id':'seal','replacement_id':'stock'},'Replace','public-seal','public-cover')

    def test_gasket_position_failed_predicate(self):
        self.game.state['parts']['stock']['location']='supply'
        self.refusal('install',{'part_id':'stock'},'public-stock','head is installed')
        self.game.state['parts']['head']['location']='tray'
        self.game.state['gasket']['active_id']='old'
        self.refusal('install',{'part_id':'stock'},'public-stock','gasket already occupies')

    def test_preparation_separates_setup_and_observation(self):
        self.refusal('prepare_condition',{'condition_id':'timing_marks_recorded'},'no recorded explicit timing setup')
        self.game.state['timing']['set_seq']=1
        self.refusal('prepare_condition',{'condition_id':'timing_marks_recorded'},'no aligned timing observation','latest setup')

    def test_restore_names_attachment_and_count_only(self):
        with patch.object(benchmark_geometry,'state_for',return_value={'installed':{'hidden-a':False,'hidden-b':False,'hidden-c':True}}):
            self.refusal('restore_attachment',{'release_id':'attachment-a'},'attachment-a','2 selected service positions')
        self.game.state['benchmark_removal']['released']['attachment-a']=False
        self.refusal('restore_attachment',{'release_id':'attachment-a'},'attachment-a','not currently released')

    def test_unknown_benchmark_identity(self):
        self.refusal('prepare_condition',{'condition_id':'bad-condition'},'condition_id','bad-condition','from look')
        self.refusal('restore_attachment',{'release_id':'bad-attachment'},'release_id','bad-attachment','from look')

    def test_schema_names_field_and_public_constraint(self):
        cases=[('measure',{'target':'a'},'missing','kind'),
               ('look',{'extra':1},'unexpected','extra'),
               ('measure',{'target':False,'kind':'flatness'},'target','string'),
               ('measure',{'target':'a','kind':'unsupported'},'kind','published choices'),
               ('check_timing',{'crank_revolutions':7},'crank_revolutions','1..6'),
               ('torque',{'part_id':'a','mode':'loosen','value_N_m':10},'angle_deg','value_N_m')]
        for name,args,*need in cases:
            with self.subTest(name=name,args=args), self.assertRaises(ValueError) as caught:
                api.validate(name,args)
            for word in need: self.assertIn(word,str(caught.exception))


if __name__=='__main__': unittest.main()
