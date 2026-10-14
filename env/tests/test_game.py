import copy
import unittest
from hgj.game import Game, replay
from hgj.fixtures import fixture_config, FixtureJoint, FixtureSoak, correct_job
from hgj.codec import digest


class GameTests(unittest.TestCase):
    def game(self, **kw):
        c = fixture_config()
        c['factors'].update(kw)
        return Game(c, joint=FixtureJoint(), soak=FixtureSoak())

    def test_inaccessible_remove_is_recorded_without_physical_change(self):
        g = self.game()
        before = copy.deepcopy(g.state['parts'])
        self.assertFalse(g.call('remove', {'part_id': 'head'})['ok'])
        self.assertEqual(before, g.state['parts'])
        self.assertEqual(len(g.records), 1)

    def test_subject_cannot_submit_state_or_unknown_fields(self):
        g = self.game()
        for tool, args in [('finish', {'state': {'pass': True}}), ('look', {'path': '/etc/passwd'}),
                           ('torque', {'part_id': 'hb01', 'value_N_m': float('nan')})]:
            self.assertFalse(g.call(tool, args)['ok'])

    def test_factor_off_hides_search_and_measurements(self):
        g = self.game(service_info=False, feedback=False)
        self.assertNotIn('search_service_info', [x['name'] for x in g.tools()])
        self.assertFalse(g.call('search_service_info', {'query': 'torque'})['ok'])
        correct_job(g, through='service')
        r = g.call('measure', {'target': 'head_face', 'kind': 'flatness'})
        self.assertEqual(r['observation'], {'feedback': 'disabled'})
        self.assertNotIn('value', str(g.call('inspect', {'target': 'hb01'})))

    def test_correct_control_and_two_replays_identical(self):
        g = self.game()
        correct_job(g)
        self.assertTrue(g.score['pass'])
        self.assertEqual(g.score['qualification'], 'software-fixture')
        a = replay(g.export(), joint=FixtureJoint(), soak=FixtureSoak())
        b = replay(g.export(), joint=FixtureJoint(), soak=FixtureSoak())
        self.assertEqual(a, b)
        self.assertEqual(a['final_state'], g.state)

    def test_control_handles_unequal_initial_thread_engagement(self):
        c=fixture_config()
        for f in c['geometry']['fasteners']:
            if f['id']=='hb01':f['initial_engagement_turns']=0.5
            if f['id']=='hb02':f['initial_engagement_turns']=1.5
        g=Game(c,joint=FixtureJoint(),soak=FixtureSoak());correct_job(g)
        self.assertTrue(g.score['pass'])
        self.assertTrue(all(r['result']['ok'] for r in g.records))

    def test_every_body_keeps_individual_identity(self):
        g = self.game()
        correct_job(g)
        self.assertEqual(set(g.state['parts']), {p['id'] for p in g.config['geometry']['parts']})
        self.assertNotEqual(g.state['parts']['hb01']['location'], g.state['parts']['gasket_old']['location'])

    def carried_config(self):
        c=fixture_config();head=next(p for p in c['geometry']['parts'] if p['id']=='head')
        head['carried_body_ids']=['cam_member','cam_retainer']
        head['carried_evidence']={'source_id':'fixture','receipt_sha256':'0'*64,'qualification':'software-fixture'}
        for pid in head['carried_body_ids']:
            c['geometry']['parts'].append({'id':pid,'role':'retained_head_member','installed':True,'removable':False,
                'requires_removed':[],'requires_installed':['head'],'source_id':'fixture'})
        c['geometry']['fasteners'].append({'id':'cam_retainer','group':'cam','service_required':False,
            'sequence_index':None,'washer_id':None,'holds':['head','cam_member'],'thread':None,
            'initial_engagement_turns':None,'spec_ref':None,'source_id':'fixture','unknown_fields':['thread']})
        return c

    def test_carried_head_members_transfer_as_distinct_bodies_and_restore(self):
        c=self.carried_config();g=Game(c,joint=FixtureJoint(),soak=FixtureSoak())
        correct_job(g,through='service')
        for pid in ('cam_member','cam_retainer'):
            self.assertEqual(g.state['parts'][pid]['location'],'tray')
            self.assertEqual(g.state['parts'][pid]['carried_with'],'head')
        self.assertFalse(g.call('install',{'part_id':'cam_member'})['ok'])
        self.assertTrue(g.call('replace',{'part_id':'gasket_old','replacement_id':g.public_id('gasket_new')})['ok'])
        self.assertTrue(g.call('install',{'part_id':g.public_id('gasket_new')})['ok'])
        self.assertTrue(g.call('install',{'part_id':'head'})['ok'])
        self.assertEqual(set(g.state['parts']),{p['id'] for p in c['geometry']['parts']})
        for pid in ('cam_member','cam_retainer'):
            self.assertEqual(g.state['parts'][pid]['location'],'assembly')
            self.assertNotIn('carried_with',g.state['parts'][pid])
        self.assertEqual(replay(g.export(),joint=FixtureJoint(),soak=FixtureSoak()),g.export())

    def test_carrier_graph_cannot_hide_required_head_bolts_or_duplicate_bodies(self):
        for bad in ('hb01','cam_member'):
            c=self.carried_config();head=next(p for p in c['geometry']['parts'] if p['id']=='head')
            head['carried_body_ids'].append(bad)
            with self.assertRaises(ValueError):Game(c)

    def test_carried_child_external_retainer_blocks_the_whole_withdrawal(self):
        c=self.carried_config()
        c['geometry']['parts'].append({'id':'external_retainer','role':'stand_retainer','installed':True,
            'removable':False,'requires_removed':[],'requires_installed':[],'source_id':'fixture'})
        c['geometry']['fasteners'].append({'id':'external_retainer','group':'stand','service_required':False,
            'sequence_index':None,'washer_id':None,'holds':['cam_member'],'thread':None,
            'initial_engagement_turns':None,'spec_ref':None,'source_id':'fixture','unknown_fields':['thread']})
        g=Game(c,joint=FixtureJoint(),soak=FixtureSoak())
        with self.assertRaises(RuntimeError):correct_job(g,through='service')
        self.assertEqual(g.state['parts']['head']['location'],'assembly')
        self.assertEqual(g.state['parts']['cam_member']['location'],'assembly')

    def test_carried_transition_backend_refusal_rolls_back_every_body(self):
        class Refusing(FixtureJoint):
            def apply(self,state,operation):
                if operation['kind']=='remove' and operation['part_id']=='head':
                    if set(operation.get('carried_body_ids',[]))!={'cam_member','cam_retainer'}:
                        raise ValueError('Missing separate carried bodies')
                    raise RuntimeError('Unqualified native group transition')
                return super().apply(state,operation)
        g=Game(self.carried_config(),joint=Refusing())
        with self.assertRaises(RuntimeError):correct_job(g,through='service')
        for pid in ('head','cam_member','cam_retainer'):
            self.assertEqual(g.state['parts'][pid]['location'],'assembly')
            self.assertNotIn('carried_with',g.state['parts'][pid])
        self.assertEqual(g.records[-1]['result']['backend_error'],'RuntimeError')

    def test_declared_fastener_carrier_refits_its_separate_washer(self):
        c=fixture_config();bolt=next(p for p in c['geometry']['parts'] if p['id']=='hb03')
        bolt['carried_body_ids']=['hw03']
        g=Game(c,joint=FixtureJoint())
        self.assertTrue(g.call('remove',{'part_id':'belt'})['ok'])
        for f in c['geometry']['fasteners']:
            if f['group']=='cover':
                self.assertTrue(g.call('torque',{'part_id':f['id'],'mode':'loosen','angle_deg':-360})['ok'])
                self.assertTrue(g.call('remove',{'part_id':f['id']})['ok'])
                self.assertTrue(g.call('remove',{'part_id':f['washer_id']})['ok'])
        self.assertTrue(g.call('remove',{'part_id':'cover'})['ok'])
        self.assertTrue(g.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
        self.assertTrue(g.call('remove',{'part_id':'hb03'})['ok'])
        self.assertEqual(g.state['parts']['hw03']['carried_with'],'hb03')
        self.assertFalse(g.call('install',{'part_id':'hw03'})['ok'])
        self.assertTrue(g.call('install',{'part_id':'hb03'})['ok'])
        for pid in ('hb03','hw03'):
            self.assertEqual(g.state['parts'][pid]['location'],'assembly')
            self.assertNotIn('carried_with',g.state['parts'][pid])
        self.assertEqual(replay(g.export(),joint=FixtureJoint()),g.export())

    def test_physics_absence_never_produces_pass(self):
        g = Game(fixture_config())
        correct_job(g)
        self.assertIsNone(g.score)
        self.assertEqual(g.export()['scoring_status'], 'unavailable')

    def test_tampered_record_config_result_and_order_refuse_replay(self):
        g = self.game(); correct_job(g)
        for mutate in [lambda x: x['actions'][0]['input'].update({'part_id':'head'}),
                       lambda x: x['actions'].pop(5),
                       lambda x: x['actions'][0]['result'].update({'ok':False}),
                       lambda x: x['config']['factors'].update({'feedback':False})]:
            r = copy.deepcopy(g.export()); mutate(r)
            with self.assertRaises(ValueError): replay(r, joint=FixtureJoint(), soak=FixtureSoak())

    def test_legacy_cli_counter_is_separate_from_tool_call_guard(self):
        c=fixture_config();c['factors'].pop('turn_budget_unit',None)
        c['factors'].update(turn_budget=2,tool_call_limit=3)
        g=Game(c,joint=FixtureJoint(),soak=FixtureSoak())
        for _ in range(3): self.assertTrue(g.call('look', {})['ok'])
        self.assertFalse(g.call('look', {})['ok'])
        self.assertEqual(g.config['factors']['turn_budget'], 2)

    def test_action_turn_budget_counts_refusals_and_blocks_finish_past_limit(self):
        c=fixture_config();c['factors'].update(turn_budget=2,turn_budget_unit='job-tool-action-attempts')
        g=Game(c,joint=FixtureJoint(),soak=FixtureSoak())
        self.assertFalse(g.call('remove',{'part_id':'head'})['ok'])
        self.assertTrue(g.call('look',{})['ok']);before=copy.deepcopy(g.state)
        self.assertEqual(g.call('look',{})['refusal'],'Environment turn budget reached')
        self.assertFalse(g.call('finish',{})['ok']);self.assertEqual(g.state,before)
        self.assertEqual(g.export()['budget'],{'unit':'job-tool-action-attempts','limit':2,'used':2,'attempted_calls':4,'exhausted':True})
        self.assertEqual(replay(g.export(),joint=FixtureJoint(),soak=FixtureSoak()),g.export())
        self.assertIsNone(g.score)

    def test_environment_budget_supports_extended_level_and_independent_guard(self):
        g=self.game(turn_budget=3,tool_call_limit=99,turn_budget_unit='job-tool-action-attempts')
        for _ in range(3):self.assertTrue(g.call('look',{})['ok'])
        self.assertFalse(g.call('look',{})['ok'])
        g=self.game(turn_budget=9,tool_call_limit=1,turn_budget_unit='job-tool-action-attempts')
        self.assertTrue(g.call('look',{})['ok'])
        self.assertEqual(g.call('look',{})['refusal'],'Tool-call guard reached')

    def test_wrong_timing_is_physical_control_not_workflow_pass(self):
        g = self.game(); correct_job(g, bad='wrong_timing')
        self.assertFalse(g.score['pass']); self.assertEqual(g.score['cause'], 'timing_error')

    def test_timing_instrument_accepts_the_sourced_six_turn_check(self):
        g=self.game()
        self.assertTrue(g.call('check_timing',{'crank_revolutions':6})['ok'])
        self.assertFalse(g.call('check_timing',{'crank_revolutions':7})['ok'])

    def test_joint_sequence_and_stretched_bolt_consequences_preserved(self):
        for bad, cause in [('wrong_torque_sequence', 'joint_distortion'),
                           ('under_torque', 'insufficient_contact'),
                           ('skipped_retorque', 'insufficient_contact'),
                           ('wrong_gasket', 'fire_ring_leak'),
                           ('reused_stretched_bolt', 'bolt_relaxation')]:
            g = self.game(); correct_job(g, bad=bad)
            self.assertFalse(g.score['pass'], bad); self.assertEqual(g.score['cause'], cause)

    def test_geometry_cycle_and_missing_edge_evidence_refuse(self):
        c = fixture_config(); c['geometry']['parts'][0]['requires_removed'] = ['head']
        next(p for p in c['geometry']['parts'] if p['id']=='head')['requires_removed'].append('block')
        with self.assertRaises(ValueError): Game(c)
        c = fixture_config(); c['geometry']['qualification'] = 'cad-derived'
        with self.assertRaises(ValueError): Game(c)

    def test_negative_torque_and_bool_numbers_rejected(self):
        g = self.game()
        for v in [-1, True, float('inf')]:
            self.assertFalse(g.call('torque', {'part_id':'hb01','value_N_m':v})['ok'])

    def test_replacement_position_and_retention_cannot_be_bypassed(self):
        g = self.game(); correct_job(g, through='service')
        self.assertFalse(g.call('replace', {'part_id':'hb03','replacement_id':'new_hb01'})['ok'])
        self.assertTrue(g.call('replace', {'part_id':'hb03','replacement_id':'new_hb03'})['ok'])
        self.assertTrue(g.call('replace', {'part_id':'gasket_old','replacement_id':g.public_id(g.role('gasket_new'))})['ok'])
        for pid in ('gasket_new','head','hw03','new_hb03'):
            self.assertTrue(g.call('install', {'part_id':g.public_id(pid)})['ok'])
        before = copy.deepcopy(g.state)
        self.assertFalse(g.call('remove', {'part_id':'hw03'})['ok'])
        self.assertFalse(g.call('remove', {'part_id':'head'})['ok'])
        self.assertEqual(g.state, before)

    def test_unmapped_bolt_supply_cannot_be_installed(self):
        g = self.game(); correct_job(g, through='service')
        for pid in ('gasket_new','head','hw01'):
            self.assertTrue(g.call('install', {'part_id':g.public_id(pid)})['ok'])
        self.assertFalse(g.call('install', {'part_id':'new_hb01'})['ok'])

    def test_retained_unresolved_fasteners_remain_separate_without_invented_values(self):
        c=fixture_config(); c['geometry']['parts'].append({'id':'retained_bolt','role':'accessory_bolt',
            'installed':True,'removable':False,'requires_removed':[],'requires_installed':[],
            'source_id':'fixture','precedence_status':'unknown','unknown_fields':['thread']})
        c['geometry']['fasteners'].append({'id':'retained_bolt','group':'accessory','service_required':False,
            'sequence_index':None,'washer_id':None,'holds':None,'thread':None,'initial_engagement_turns':None,
            'spec_ref':None,'source_id':'fixture','unknown_fields':['thread','holds','initial_engagement_turns']})
        g=Game(c,joint=FixtureJoint(),soak=FixtureSoak())
        self.assertIsNone(g.state['bolts']['retained_bolt']['turns'])
        self.assertIsNone(g.state['bolts']['retained_bolt']['torque_N_m'])
        self.assertFalse(g.call('remove',{'part_id':'retained_bolt'})['ok'])
        self.assertFalse(g.call('torque',{'part_id':'retained_bolt','mode':'tighten','value_N_m':20})['ok'])
        correct_job(g); self.assertEqual(g.state['parts']['retained_bolt']['location'],'assembly')

    def test_supply_observations_do_not_disclose_correctness_flags(self):
        c=fixture_config(); c['policy']['public_observation']='technician-v2'; g=Game(c)
        view=g.call('look',{})
        labels={p[k] for p in view['parts'] for k in ('id','role')}
        self.assertNotIn('gasket_wrong',labels); self.assertNotIn('gasket_new',labels)
        stocks=[p for p in view['parts'] if p['role']=='head_gasket' and p['location']=='supply']
        self.assertEqual(len(stocks),2); self.assertNotEqual(stocks[0]['id'],stocks[1]['id'])
        self.assertTrue(g.call('inspect',{'target':stocks[0]['id']})['ok'])
        self.assertFalse(g.call('install',{'part_id':'gasket_wrong'})['ok'])

    def test_nonfinite_attempts_replay_and_backend_exceptions_roll_back(self):
        g=self.game(); g.call('torque',{'part_id':'hb01','mode':'tighten','value_N_m':float('nan')})
        self.assertEqual(replay(g.export(),joint=FixtureJoint(),soak=FixtureSoak()),g.export())
        class BrokenJoint(FixtureJoint):
            def apply(self,state,operation): raise RuntimeError('internal numerical failure')
        g=Game(fixture_config(),joint=BrokenJoint()); before=copy.deepcopy(g.state)
        result=g.call('torque',{'part_id':'cb01','mode':'loosen','angle_deg':-120})
        self.assertFalse(result['ok']); self.assertEqual(result['backend_error'],'RuntimeError')
        self.assertEqual(g.state,before); self.assertEqual(len(g.records),1)

    def test_replacement_does_not_edit_opaque_backend_state_before_apply(self):
        class BoundJoint(FixtureJoint):
            def initialize(self,config):
                s=super().initialize(config); s['state_sha256']=digest(s); return s
            def apply(self,state,operation):
                prior=state.pop('state_sha256')
                if prior!=digest(state): raise ValueError('Model state was modified outside the backend')
                s=super().apply(state,operation); s['state_sha256']=digest(s); return s
        g=Game(fixture_config(),joint=BoundJoint()); correct_job(g,through='service')
        self.assertTrue(g.call('replace',{'part_id':'hb03','replacement_id':'new_hb03'})['ok'])

    def test_nullable_diagnostic_warpage_is_not_converted_to_zero(self):
        class Diagnostic(FixtureJoint):
            def initialize(self,config):
                s=super().initialize(config); s.update({'qualification':'rigid-reference-component-only',
                    'head_warpage_m':None,'acceptance_eligible':False,'missing_physics':['head bending']}); return s
        g=Game(fixture_config(),joint=Diagnostic())
        self.assertIsNone(g.state['joint']['head_warpage_m'])
        self.assertTrue(g.call('look',{})['ok'])
        correct_job(g,through='service')
        self.assertIsNone(g.call('measure',{'target':'head_face','kind':'flatness'})['observation']['value'])

    def test_ineligible_joint_cannot_receive_physical_credit(self):
        class Ineligible(FixtureJoint):
            def initialize(self,config):
                s=super().initialize(config);s['acceptance_eligible']=False;return s
        class WronglyQualified(FixtureSoak):
            def score(self,job):
                s=super().score(job);s['qualification']='validated-physics';return s
        g=Game(fixture_config(),joint=Ineligible(),soak=WronglyQualified());correct_job(g)
        self.assertIsNone(g.score['pass']);self.assertEqual(g.score['status'],'INVALID_INPUT')

    def test_finish_hides_physics_internals_but_retains_trusted_score(self):
        class DetailedSoak(FixtureSoak):
            def score(self,job):
                s=super().score(job)
                s.update({'interval_journal':[{'private_margin':123}],
                          'internal_state':{'source_path':'private/model.py'}})
                return s
        g=Game(fixture_config(),joint=FixtureJoint(),soak=DetailedSoak());correct_job(g)
        public=g.records[-1]['result']['score']
        self.assertEqual(set(public),{'status','qualification','pass','time_to_failure_s','cause'})
        self.assertNotIn('interval_journal',public);self.assertNotIn('model_sha256',public)
        self.assertIn('interval_journal',g.export()['score'])
        self.assertEqual(replay(g.export(),joint=FixtureJoint(),soak=DetailedSoak()),g.export())


if __name__ == '__main__': unittest.main()
