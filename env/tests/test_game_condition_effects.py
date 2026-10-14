"""Tiny in-process transport controls; synthetic receipts admit no real physics.

The temporary pinned stdlib facade tests consumer plumbing only. No native model,
subject, CLI, wall-time experiment, or complete control set is executed here.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from hgj.backends import Backend
from hgj.codec import digest, file_digest
from hgj.game import Game, replay
from tests.test_initial_conditions import InitialConditionsTests


SOURCE = '''import copy,hashlib,json
def digest(v):
    return hashlib.sha256((json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+chr(10)).encode()).hexdigest()
def initialize(config):
    return {'bolt_tensions_N':{f['id']:0 for f in config['geometry']['fasteners'] if f['group']=='head'},
        'head_warpage_m':None,'acceptance_eligible':False,'qualification':'rigid-reference-component-only',
        'missing_physics':['Synthetic transport only'],'fault':config.get('transport_test_fault')}
def apply(state,op):
    out=copy.deepcopy(state)
    if state['fault']=='exception':raise ArithmeticError('Synthetic transport fault')
    if state['fault']=='operation_mutation':op['bolts']['hb01']['stretch_mm']=99
    if op['kind']=='clean':values={'/surfaces/cover_face/residue_fraction':0.25,'/surfaces/cover_face/dry':False}
    elif op['kind']=='check_timing':
        values={'/timing/checks':op['before_conditions']['timing']['checks']+[{'seq':op['attempt_sequence'],
            'crank_revolutions':op['crank_revolutions'],'marks_align':False}]}
        if state['fault']=='timing_request':values['/timing/checks'][-1]['crank_revolutions']=1
        if state['fault']=='timing_rewrite':values['/timing/checks']=values['/timing/checks'][-1:]
        if state['fault']=='timing_unknown':values['/timing/checks'][-1]['marks_align']=None
    elif op['kind']=='install':values={'/timing/cam_phase_deg':12,'/timing/crank_phase_deg':-2}
    else:values={'/parts/belt/damaged':False}
    with open(__file__,'rb') as handle:pin=hashlib.sha256(handle.read()).hexdigest()
    if state['fault']=='source':pin='b'*64
    fields={path:{'value':value,'source_sha256':pin,'status':'estimated','note':'Synthetic transport only'} for path,value in values.items()}
    if state['fault']=='extra':fields['/bolts/hb01/stretch_mm']={'value':0,'source_sha256':pin,'status':'estimated','note':'Forbidden extra'}
    out['condition_effects']={'schema':'hgj/action-conditions/v1','operation_sha256':digest(op),
        'before_conditions_sha256':op['before_conditions_sha256'],'fields':fields}
    if state['fault']=='hash':out['condition_effects']['operation_sha256']='b'*64
    out['head_warpage_m']=0.5
    return out
def score(job):raise AssertionError('Unknown final state reached scoring')
'''


class GameConditionEffectsTests(unittest.TestCase):
    def fixture(self, fault=None, belt_installed=True):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        path=Path(directory.name)/'transport_facade.py';path.write_text(SOURCE)
        config=InitialConditionsTests().config()
        for part in config['geometry']['parts']:
            if part['id']=='cover' or part['id']=='belt' and not belt_installed:part['installed']=False
        initial=config['initial_conditions']
        initial['geometry_sha256']=digest(config['geometry'])
        initial['values']['parts']['cover']['location']='supply'
        if not belt_installed:initial['values']['parts']['belt']['location']='supply'
        config['policy']['public_observation']='technician-v2'
        config['factors']['turn_budget_unit']='job-tool-action-attempts'
        config['transport_test_fault']=fault
        descriptor={'schema':'hgj/backend/v1','kind':'joint','qualification':'validated-physics',
                    'module':str(path),'sha256':file_digest(path),'dependencies':[]}
        source=descriptor['sha256']
        specs=[('clean',{'target':'cover_face','method':'solvent','protect_openings':True},
                ['/surfaces/cover_face/residue_fraction','/surfaces/cover_face/dry']),
               ('remove',{'part_id':'belt'},['/parts/belt/damaged']),
               ('install',{'part_id':'belt','cam_phase_deg':0,'crank_phase_deg':0},
                ['/timing/cam_phase_deg','/timing/crank_phase_deg']),
               ('check_timing',{'crank_revolutions':4},['/timing/checks'])]
        rules=[{'id':'transport-'+name,'tool':name,'arguments':args,'supported':True,
            'required_paths':paths,'fields':{p:{'source_pins':[source],'statuses':['estimated']} for p in paths},
            'validation_sha256':'e'*64,'reason':'Synthetic consumer transport only'} for name,args,paths in specs]
        domain={'schema':'hgj/action-domains/v1','qualification':'source-defined',
            'geometry_sha256':digest(config['geometry']),'initial_conditions_sha256':digest(initial),
            'variant_sha256':digest(config['variants'][0]),'joint_descriptor_sha256':digest(descriptor),
            'rules':rules,'default_reason':'All unlisted commands unsupported in this transport test'}
        config['action_domains']=domain
        config['admission']={'schema':'hgj/admission/v1','status':'validated-physics',
            'geometry_sha256':digest(config['geometry']),'initial_conditions_sha256':digest(initial),
            'joint_descriptor_sha256':digest(descriptor),'soak_descriptor_sha256':'f'*64,'validation_sha256':'e'*64,
            'action_domains_sha256':digest(domain),'action_domains_body_sha256':digest(domain),
            'action_rule_validation_sha256':{r['id']:r['validation_sha256'] for r in rules}}
        domain_path=Path(directory.name)/'transport_domain.json'
        domain_path.write_text(json.dumps(domain,indent=2,ensure_ascii=False))
        config['identity']={'action_domains_sha256':file_digest(domain_path)}
        config['admission']['action_domains_sha256']=file_digest(domain_path)
        return config,Backend(descriptor,config['admission'])

    def test_source_values_private_custody_and_exact_replay(self):
        config,backend=self.fixture();game=Game(config,joint=backend)
        initial_warp=config['initial_conditions']['values']['surfaces']['head_face']['warpage_m']
        self.assertEqual(game.state['surfaces']['head_face']['warpage_m'],initial_warp)
        args=config['action_domains']['rules'][0]['arguments']
        result=game.call('clean',args);self.assertTrue(result['ok'],result)
        self.assertNotIn('authorized_condition_effects',result)
        self.assertEqual(game.state['surfaces']['cover_face']['residue_fraction'],0.25)
        self.assertFalse(game.state['surfaces']['cover_face']['dry'])
        self.assertNotIn('tube_seals_oiled',game.state['surfaces']['cover_face'])
        self.assertEqual(game.state['surfaces']['head_face']['warpage_m'],initial_warp)
        record=game.export();effect=record['actions'][0]['authorized_condition_effects']
        self.assertEqual(effect['operation']['before_conditions'],config['initial_conditions']['values'])
        self.assertEqual(effect['operation_sha256'],digest(effect['operation']))
        self.assertEqual(replay(record,joint=backend),record)
        altered=copy.deepcopy(record);altered['actions'][0]['authorized_condition_effects']['rule_id']='other'
        with self.assertRaisesRegex(ValueError,'Action replay mismatch'):replay(altered,joint=backend)

    def test_invalid_whole_packet_is_atomic_and_counted(self):
        for fault in ('source','extra','hash','exception','operation_mutation'):
            with self.subTest(fault=fault):
                config,backend=self.fixture(fault);game=Game(config,joint=backend)
                before=copy.deepcopy(game.state);mapping=copy.deepcopy(game.fasteners)
                result=game.call('remove',{'part_id':'belt'})
                self.assertFalse(result['ok'],result)
                self.assertEqual(game.state,before);self.assertEqual(game.fasteners,mapping)
                self.assertEqual(game.budget()['used'],1)
                self.assertEqual(replay(game.export(),joint=backend),game.export())

    def test_unlisted_command_refuses_before_backend_and_bare_object_is_not_admitted(self):
        config,backend=self.fixture('exception');game=Game(config,joint=backend)
        result=game.call('clean',{'target':'cover_face','method':'abrasive_disc'})
        self.assertEqual(result['refusal'],'Source-defined physical action effects are not admitted')
        class Bare:
            descriptor=backend.descriptor
            def initialize(self,c):return backend.initialize(c)
            def apply(self,s,o):raise AssertionError('Unpinned object reached')
        with self.assertRaisesRegex(ValueError,'exact source backend'):Game(config,joint=Bare())

    def test_command_structure_survives_condition_commit_and_timing_is_source_defined(self):
        config,backend=self.fixture(belt_installed=False);game=Game(config,joint=backend)
        result=game.call('install',{'part_id':'belt','cam_phase_deg':0,'crank_phase_deg':0})
        self.assertTrue(result['ok'],result);self.assertEqual(game.state['parts']['belt']['location'],'assembly')
        self.assertEqual(game.state['timing']['cam_phase_deg'],12)
        result=game.call('check_timing',{'crank_revolutions':4})
        self.assertEqual(result['observation'],{'marks_align':False})
        self.assertEqual(len(game.state['timing']['checks']),1)
        self.assertEqual(replay(game.export(),joint=backend),game.export())
        config['factors']['feedback']=False;other=Game(config,joint=backend)
        self.assertTrue(other.call('install',{'part_id':'belt','cam_phase_deg':0,'crank_phase_deg':0})['ok'])
        self.assertEqual(other.call('check_timing',{'crank_revolutions':4})['observation'],{'feedback':'disabled'})
        self.assertEqual(len(other.state['timing']['checks']),1)

    def test_timing_evidence_cannot_rewrite_history_or_change_requested_revolutions(self):
        for fault in ('timing_request','timing_rewrite','timing_unknown'):
            config,backend=self.fixture(fault);game=Game(config,joint=backend)
            if fault=='timing_rewrite':self.assertTrue(game.call('check_timing',{'crank_revolutions':4})['ok'])
            before=copy.deepcopy(game.state)
            self.assertFalse(game.call('check_timing',{'crank_revolutions':4})['ok'])
            self.assertEqual(game.state,before)

    def test_unknown_sourced_final_condition_is_non_score_before_soak(self):
        config,backend=self.fixture()
        initial=config['initial_conditions'];initial['values']['surfaces']['head_face']['warpage_m']=None
        initial['field_sources']['/surfaces/head_face/warpage_m']['status']='unknown'
        config['admission']['initial_conditions_sha256']=digest(initial)
        domain=config['action_domains'];domain['initial_conditions_sha256']=digest(initial)
        domain_path=Path(backend.descriptor['module']).parent/'transport_domain.json'
        domain_path.write_text(json.dumps(domain,indent=2,ensure_ascii=False))
        config['identity']['action_domains_sha256']=file_digest(domain_path)
        config['admission'].update(action_domains_sha256=file_digest(domain_path),action_domains_body_sha256=digest(domain))
        soak_descriptor={**backend.descriptor,'kind':'soak'}
        config['admission']['soak_descriptor_sha256']=digest(soak_descriptor)
        backend=Backend(backend.descriptor,config['admission'])
        soak=Backend(soak_descriptor,config['admission'])
        game=Game(config,joint=backend,soak=soak)
        result=game.call('finish',{});self.assertTrue(result['ok'],result)
        self.assertEqual(result['score']['status'],'INVALID_INPUT');self.assertIsNone(result['score']['pass'])
        self.assertEqual(replay(game.export(),joint=backend,soak=soak),game.export())

    def test_invalid_domain_refuses_before_joint_initialization(self):
        config,backend=self.fixture();config['action_domains']['rules'][0]['arguments']['oil']=True
        class Unreachable:
            def initialize(self,c):raise AssertionError('Domain failed to refuse before initialization')
        with self.assertRaisesRegex(ValueError,'domain file/body'):Game(config,joint=Unreachable())

    def test_failure_after_validated_effect_has_explicit_uncommitted_packet(self):
        config,backend=self.fixture();config['labor']['actions']['clean']['seconds']='invalid'
        game=Game(config,joint=backend);before=copy.deepcopy(game.state)
        result=game.call('clean',config['action_domains']['rules'][0]['arguments'])
        self.assertFalse(result['ok']);self.assertEqual(game.state,before)
        self.assertIs(game.records[-1]['condition_effects_committed'],False)
        self.assertIn('authorized_condition_effects',game.records[-1])
        self.assertEqual(replay(game.export(),joint=backend),game.export())

    def test_timing_evidence_sequence_counts_prior_refusal(self):
        config,backend=self.fixture();game=Game(config,joint=backend)
        self.assertFalse(game.call('clean',{'target':'cover_face','method':'abrasive_disc'})['ok'])
        result=game.call('check_timing',{'crank_revolutions':4});self.assertTrue(result['ok'],result)
        self.assertEqual(game.state['timing']['checks'][-1]['seq'],2)
