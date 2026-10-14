"""Small authored source-policy trajectories; never execute an environment."""
from copy import deepcopy
import unittest
from job_accuracy.independent import fingerprint,AssessmentInputError
from job_accuracy import removal


def sample():
    binding={'CAD_sha256':'a'*64,'installed_pose':{'position_m':[0,0,0],'quaternion_wxyz':[1,0,0,0]}}
    rows=[{'id':'head_source','mode':'individual','binding':binding,'routes':[{'id':'supported',
        'preconditions':{'all':[{'released':'tie'},{'condition':{'id':'cold','equals':True}}]},'carried_body_ids':['member_source']}]},
        {'id':'member_source','mode':'carried_with_assembly','binding':binding,'routes':[],'carrier_ids':['head_source']},
        {'id':'base_source','mode':'retained_for_job','binding':binding,'routes':[]}]
    policy={'schema':'engine-cad/benchmark-removal-policy/v1','physical_qualification':False,'parts':rows,
            'condition_ids':['cold'],'release_actions':['tie'],
            'release_action_definitions':[{'id':'tie','preconditions':{'installed':'base_source'}}]}
    source={'head_source':'head','member_source':'member','base_source':'base'}
    parts=[{'id':body,'role':'head' if body=='head' else 'source_component','installed':True,
            'requires_removed':[],'requires_installed':[], 'l1_selected_body':True,'l1_body_id':key,'l1_binding':binding}
           for key,body in source.items()]
    spec={'policy':policy,'policy_semantic_sha256':fingerprint(policy),'policy_sha256':'b'*64,'source_to_body':source}
    config={'benchmark_removal':spec,'geometry':{'parts':parts,'fasteners':[]},'variant_id':'authored','policy':{}}
    attachments=[{'seq':1,'action':'prepare_condition','condition_id':'cold'},
                 {'seq':2,'action':'release_attachment','release_id':'tie'},
                 {'seq':5,'action':'restore_attachment','release_id':'tie'}]
    movements=[{'seq':3,'action':'remove','body_id':'head','source_body_id':'head_source','route_id':'supported','carried_body_ids':['member']},
               {'seq':4,'action':'install','body_id':'head','source_body_id':'head_source','carried_body_ids':['member']}]
    records=[{'seq':1,'name':'prepare_condition','input':{'condition_id':'cold'},'result':{'ok':True,'receipt':attachments[0]}},
             {'seq':2,'name':'release_attachment','input':{'release_id':'tie'},'result':{'ok':True,'receipt':attachments[1]}},
             {'seq':3,'name':'remove','input':{'part_id':'head','route_id':'supported'},'result':{'ok':True,'carried_body_ids':['member']}},
             {'seq':4,'name':'install','input':{'part_id':'head'},'result':{'ok':True,'carried_body_ids':['member']}},
             {'seq':5,'name':'restore_attachment','input':{'release_id':'tie'},'result':{'ok':True,'receipt':attachments[2]}}]
    final={'parts':{body:{'location':'assembly'} for body in source.values()},'benchmark_removal':{
        'policy_sha256':'b'*64,'released':{'tie':False},'conditions':{'cold':True},'replacements':{},
        'movements':movements,'attachment_history':attachments,'physical_qualification':False}}
    return config,records,final


def repin(config):
    config['benchmark_removal']['policy_semantic_sha256']=fingerprint(config['benchmark_removal']['policy'])


class SourceRemoval(unittest.TestCase):
    def test_complete_trace_reconstructs_carried_and_retained_positions(self):
        r=removal.replay(*sample());self.assertTrue(r['valid_disassembly']);self.assertTrue(r['reassembly_complete'])
        self.assertEqual(r['source_positions'],3)
        self.assertEqual([p['source_position'] for p in r['positions'] if p['moved']],['head_source','member_source'])

    def test_missing_attachment_cannot_be_hidden_by_final_restored_flag(self):
        c,a,f=sample();a[1]['result']['ok']=False
        r=removal.replay(c,a,f);self.assertFalse(r['valid_disassembly']);self.assertFalse(r['reassembly_complete'])
        self.assertTrue(any('route-prerequisites' in row['reasons'] for row in r['invalid_attempts']))

    def test_carried_set_is_compared_with_both_action_and_final_journal(self):
        c,a,f=sample();a[2]['result']['carried_body_ids']=[]
        self.assertFalse(removal.replay(c,a,f)['valid_disassembly'])
        c,a,f=sample();f['benchmark_removal']['movements'][0]['carried_body_ids']=[]
        self.assertIn('movements/0',removal.replay(c,a,f)['state_mismatches'])

    def test_retained_body_cannot_be_removed_as_an_individual(self):
        c,a,f=sample();a[2]['input']['part_id']='base'
        r=removal.replay(c,a,f);self.assertFalse(r['valid_disassembly'])
        self.assertIn('individual-removal-not-permitted',r['invalid_attempts'][0]['reasons'])

    def test_wrong_route_and_missing_current_body_fail(self):
        c,a,f=sample();a[2]['input']['route_id']='undeclared'
        self.assertFalse(removal.replay(c,a,f)['valid_disassembly'])
        c,a,f=sample();f['parts']['member']['location']='tray'
        self.assertFalse(removal.replay(c,a,f)['reassembly_complete'])

    def test_restoration_before_reinstallation_is_invalid(self):
        c,a,f=sample();a[3],a[4]=a[4],a[3]
        r=removal.replay(c,a,f);self.assertTrue(r['valid_disassembly']);self.assertFalse(r['reassembly_complete'])
        self.assertTrue(any('attachment-restoration-order' in row['reasons'] for row in r['invalid_attempts']))

    def test_condition_truth_does_not_accept_integer_one(self):
        node={'condition':{'id':'x','equals':True}}
        self.assertFalse(removal.predicate(node,{}, {},{'x':1}))
        self.assertTrue(removal.predicate(node,{}, {},{'x':True}))
        self.assertTrue(removal.predicate({'all':[]},{},{},{}))
        self.assertTrue(removal.predicate({'any':[{'installed':'a'},{'installed':'b'}]},{'a':False,'b':True},{},{}))

    def test_policy_and_binding_changes_are_named_refusals(self):
        for code,change in [
            ('removal-policy-identity',lambda c:c['benchmark_removal']['policy'].update(physical_qualification=True)),
            ('removal-source-census',lambda c:c['benchmark_removal']['source_to_body'].update(head_source='base')),
            ('removal-attachment-census',lambda c:c['benchmark_removal']['policy']['release_actions'].append('extra')),
            ('removal-route-domain',lambda c:c['benchmark_removal']['policy']['parts'][0].update(mode='invented')),
            ('removal-route-domain',lambda c:c['benchmark_removal']['policy']['parts'][0].update(routes=[])),
            ('removal-route-domain',lambda c:c['benchmark_removal']['policy']['parts'][1].pop('carrier_ids')),
            ('removal-attachment-census',lambda c:c['benchmark_removal']['policy']['release_actions'].append('tie')),
            ('removal-moving-census',lambda c:c['benchmark_removal']['policy']['parts'][0]['routes'][0]['carried_body_ids'].append('member_source'))]:
            c,a,f=sample();change(c)
            if code!='removal-policy-identity':repin(c)
            with self.subTest(code=code),self.assertRaisesRegex(AssessmentInputError,code):removal.replay(c,a,f)

    def test_predicate_domains_are_named_refusals(self):
        for code,node,state in [
            ('removal-predicate-shape',{'all':[],'any':[]},({}, {}, {})),
            ('removal-predicate-branch',{'any':[]},({}, {}, {})),
            ('removal-predicate-operator',{'invented':'a'},({'a':True}, {}, {})),
            ('removal-condition-domain',{'condition':{'id':'x','equals':None}},({}, {}, {'x':False})),
            ('removal-state-domain',{'installed':'x'},({'x':1}, {}, {}))]:
            with self.subTest(code=code),self.assertRaisesRegex(AssessmentInputError,code):removal.predicate(node,*state)
        deep={'all':[]}
        for _ in range(removal.MAX_PREDICATE_DEPTH+1):deep={'all':[deep]}
        with self.assertRaisesRegex(AssessmentInputError,'removal-predicate-bound'):removal.predicate(deep,{},{},{})

if __name__=='__main__':unittest.main()

class SourceCheckpointIntegration(unittest.TestCase):
    def joined(self):
        from test_checkpoint_chronology import base,rechain
        r=base();c,a,f=sample();names={'head':'authored_carrier','member':'authored_member','base':'authored_base'}
        for p in c['geometry']['parts']:
            p['id']=names[p['id']];p['role']='source_component'
        c['benchmark_removal']['source_to_body']={key:names[value] for key,value in c['benchmark_removal']['source_to_body'].items()}
        for row in a:
            if 'part_id' in row['input']:row['input']['part_id']=names[row['input']['part_id']]
            if 'carried_body_ids' in row['result']:row['result']['carried_body_ids']=[names[x] for x in row['result']['carried_body_ids']]
        offset=len(r['actions'])-1
        for row in f['benchmark_removal']['movements']:
            row['seq']+=offset;row['body_id']=names[row['body_id']];row['carried_body_ids']=[names[x] for x in row['carried_body_ids']]
        for row in f['benchmark_removal']['attachment_history']:row['seq']+=offset
        r['config']['geometry']['parts'].extend(c['geometry']['parts']);r['config']['benchmark_removal']=c['benchmark_removal']
        for body in names.values():
            for state in (r['final_state'],r['config']['repair_scoring']['reference']['final']):
                state['parts'][body]={'location':'assembly','damaged':False}
        r['final_state']['benchmark_removal']=f['benchmark_removal'];r['actions'][-1:-1]=a
        return rechain(r)

    def test_full_record_checkpoint_join(self):
        from tools.test_repair_checkpoints import evaluate
        p=evaluate(self.joined())['primary_score'];self.assertEqual(p['points_earned'],18)

    def test_final_attachment_failure_is_reassembly_not_disassembly(self):
        from test_checkpoint_chronology import rechain
        from tools.test_repair_checkpoints import evaluate
        r=self.joined();r['final_state']['benchmark_removal']['released']['tie']=True
        p=evaluate(rechain(r))['primary_score']
        self.assertTrue(next(x for x in p['checkpoints'] if x['id']=='CP02')['passed'])
        self.assertFalse(next(x for x in p['checkpoints'] if x['id']=='CP12')['passed'])

    def test_removal_journal_corruption_fails_disassembly_evidence(self):
        from test_checkpoint_chronology import rechain
        from tools.test_repair_checkpoints import evaluate
        r=self.joined();r['final_state']['benchmark_removal']['movements'][0]['carried_body_ids']=[]
        p=evaluate(rechain(r))['primary_score']
        self.assertFalse(next(x for x in p['checkpoints'] if x['id']=='CP02')['passed'])
