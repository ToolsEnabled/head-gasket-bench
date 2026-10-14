"""Owned value fixtures for the compact/full custody boundary, no Game calls."""
import copy
import unittest
from job_accuracy import transport
from job_accuracy.independent import encoded,AssessmentInputError


class CompactFinish(unittest.TestCase):
    def setUp(self):
        self.score={'schema':'hgj/repair-score/v1','status':'scored','tool_calls':1,
            'bolt_accuracy':{'correct':60,'total':60,'accuracy_percent':100},
            'checklist_accuracy':{'correct':1,'total':1,'accuracy_percent':100},
            'human_time':{'productive_seconds':120,'penalty_seconds':0,'total_seconds':120,'reference_seconds':13630},
            'mistakes':{'count':0,'by_type':{}},
            'primary_score':{'schema':'test-primary','points_earned':18,'total_points':18,'S_full':1,'S_partial':1.0}}
        self.record={'score':copy.deepcopy(self.score),'finished':True,'scoring_status':'scored',
                     'actions':[{'name':'finish','result':{'ok':True,'score':copy.deepcopy(self.score),'turns_remaining':1023}}]}
        self.raw=encoded(self.record)
        self.value={'ok':True,'schema':'hgj/finish-summary/v1','scoring_status':'scored',
                    'score_summary':copy.deepcopy(self.score),'turns_remaining':1023,
                    'record':{'file':'finish-record.json','sha256':transport.sha(self.raw),'bytes':len(self.raw)}}

    def test_valid_join(self):
        transport.compact_finish(self.record,self.record['actions'][-1],self.value,self.raw)

    def test_compact_scalars_and_pointer(self):
        mutations=[('count',lambda v:v['score_summary']['mistakes'].update(count=False)),
                   ('points',lambda v:v['score_summary']['primary_score'].update(points_earned=17)),
                   ('hash',lambda v:v['record'].update(sha256='0'*64)),
                   ('path',lambda v:v['record'].update(file='../finish-record.json')),
                   ('bytes',lambda v:v['record'].update(bytes=len(self.raw)+1))]
        for name,change in mutations:
            with self.subTest(name=name):
                value=copy.deepcopy(self.value);change(value)
                with self.assertRaisesRegex(AssessmentInputError,'transport-finish-projection'):
                    transport.compact_finish(self.record,self.record['actions'][-1],value,self.raw)

    def test_snapshot_required_and_exact(self):
        for raw in (None,self.raw+b' ',encoded({'wrong':'record'})):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(AssessmentInputError,'transport-finish-snapshot'):
                    transport.compact_finish(self.record,self.record['actions'][-1],self.value,raw)

    def test_successful_final_finish_required(self):
        action=copy.deepcopy(self.record['actions'][-1])
        with self.assertRaisesRegex(AssessmentInputError,'transport-finish-witness'):
            transport.compact_finish(self.record,action,self.value,self.raw)


if __name__=='__main__':unittest.main()
