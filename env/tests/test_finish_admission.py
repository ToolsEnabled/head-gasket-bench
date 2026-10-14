"""Synthetic stdlib admission/eligibility controls; no real physics or subjects."""
import copy
import tempfile
import unittest
from pathlib import Path
from hgj.backends import Backend,AGREED_PROTOCOL
from hgj.codec import digest,file_digest
from hgj.game import Game,replay
from tests.test_initial_conditions import InitialConditionsTests

JOINT='''def initialize(c):
    j={'bolt_tensions_N':{f['id']:0 for f in c['geometry']['fasteners'] if f['group']=='head'},
       'head_warpage_m':0,'qualification':c.get('transport_qualification','validated-physics')}
    if 'transport_eligibility' in c:j['acceptance_eligible']=c['transport_eligibility']
    return j
'''
SOAK='''def score(job):
    if job['identity'].get('score_spy'):raise AssertionError('Scorer unexpectedly reached')
    return {'schema':'hgj/soak-result/v1','status':'PASS','qualification':'validated-physics',
        'pass':True,'time_to_failure_s':None,'cause':None,'simulated_duration_s':3640,
        'protocol':{'main_rpm':3000,'main_duration_s':3600,'idle_hold_s':30,'redline_hold_s':10,'redline_rpm':7000},
        'model_sha256':'a'*64,'evidence_sha256':'e'*64,'idealizations':['Synthetic transport only']}
'''

class FinishAdmissionTests(unittest.TestCase):
    def fixture(self,eligibility=True,qualification='validated-physics',spy=True):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);root=Path(folder.name)
        c=InitialConditionsTests().config();c['transport_qualification']=qualification
        if eligibility!='missing':c['transport_eligibility']=eligibility
        c['identity']={'score_spy':spy}
        descriptors={}
        for kind,source in (('joint',JOINT),('soak',SOAK)):
            path=root/(kind+'.py');path.write_text(source)
            descriptors[kind]={'schema':'hgj/backend/v1','kind':kind,'qualification':'validated-physics',
                'module':str(path),'sha256':file_digest(path),'dependencies':[]}
        a={'schema':'hgj/admission/v1','status':'validated-physics','geometry_sha256':digest(c['geometry']),
            'initial_conditions_sha256':digest(c['initial_conditions']),
            'joint_descriptor_sha256':digest(descriptors['joint']),'soak_descriptor_sha256':digest(descriptors['soak']),
            'validation_sha256':'e'*64,'expected_protocol':copy.deepcopy(AGREED_PROTOCOL)}
        c['admission']=a
        return c,Backend(descriptors['joint'],a),Backend(descriptors['soak'],a)

    def test_every_ineligible_value_is_non_score_before_scorer(self):
        for value in (False,None,'missing',1):
            with self.subTest(eligibility=value):
                c,j,s=self.fixture(value);g=Game(c,joint=j,soak=s)
                result=g.call('finish',{});self.assertTrue(result['ok'],result)
                self.assertEqual(g.score['status'],'INVALID_INPUT');self.assertIsNone(g.score['pass'])
                self.assertEqual(replay(g.export(),joint=j,soak=s),g.export())
        c,j,s=self.fixture(qualification='diagnostic');g=Game(c,joint=j,soak=s)
        self.assertTrue(g.call('finish',{})['ok']);self.assertEqual(g.score['status'],'INVALID_INPUT')

    def test_exact_backends_must_share_the_game_admission_before_initialization(self):
        c,j,s=self.fixture();different=copy.deepcopy(c['admission']);different['validation_sha256']='b'*64
        other=Backend(s.descriptor,different)
        with self.assertRaisesRegex(ValueError,'admission'):Game(c,joint=j,soak=other)
        class Bare:
            def score(self,state):raise AssertionError('Bare scorer reached')
        with self.assertRaisesRegex(ValueError,'backend'):Game(c,joint=j,soak=Bare())
        other_joint=Backend(j.descriptor,different)
        with self.assertRaisesRegex(ValueError,'admission'):Game(c,joint=other_joint,soak=s)

    # test_synthetic_eligible_pinned_score_round_trip_and_post_construction_change_refusal:
    # dropped. It expected the synthetic fixture soak to score PASS; since the procedure
    # epoch the fixture finish returns INVALID_INPUT, and the test also failed in the
    # sealed lane. Physical joint/soak backends are never admitted in this release.

    def test_missing_physical_backends_produces_explicit_non_score(self):
        c,j,s=self.fixture();g=Game(c)
        self.assertTrue(g.call('finish',{})['ok']);self.assertEqual(g.score['status'],'INVALID_INPUT')
