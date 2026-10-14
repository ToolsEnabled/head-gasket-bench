"""Measured scripted process time stays distinct from agent and analysis time."""
from copy import deepcopy
import unittest
from job_accuracy import usage
from job_accuracy.independent import fingerprint,AssessmentInputError


def example():
    score={k:{} for k in ('human_time','mistakes','bolt_accuracy','checklist_accuracy','coverage','primary_score')};score['reference_sha256']='ref'
    r={'score':score,'score_sha256':fingerprint(score),'finished':True,'actions':[{'name':'finish','result':{'ok':True}}]}
    e={'schema':'hgj/repair-run-report/v1','run_sha256':fingerprint(r),'score_sha256':r['score_sha256'],**deepcopy(score),
       'finished':True,'status':'finished','terminal_reason':'finished','tool_calls':{'attempted':1,'successful':1,'refused':0},
       'real_time':{'seconds':1.25,'source':'Authored scripted server process'},
       'tokens':{'input':0,'output':0,'total':0,'status':'recorded','source':'Authored no-provider control'}}
    p=[{'label':'case'+suffix,'exit_code':0,'wall_seconds':wall,'stdin_bytes':3,'stdout_bytes':5,'stderr_bytes':0}
       for suffix,wall in [('',1.25),('-replay-1',2.5),('-replay-2',0)]]
    return [r,e,p,{'provider_calls':0,'model_calls':0},'case',{'stdin':b'abc','stdout':b'12345','stderr':b''}]


def corruptions():
    rows=[]
    def add(gate,change):
        a=example();change(a);rows.append((gate,a))
    add('usage-record-binding',lambda a:a[1].update(run_sha256='other'))
    add('usage-score-fields',lambda a:a[1]['human_time'].update(total_seconds=1))
    add('usage-completion-counts',lambda a:a[1]['tool_calls'].update(refused=False))
    add('usage-completion-counts',lambda a:a[1].update(finished=1))
    add('usage-performance-census',lambda a:a[2].append(deepcopy(a[2][0])))
    add('usage-process-results',lambda a:a[2][0].update(exit_code=False))
    add('usage-process-results',lambda a:a[2][1].update(wall_seconds=-1))
    add('usage-process-results',lambda a:a[2][1].update(stderr_bytes=False))
    add('usage-server-stream-bytes',lambda a:a[5].update(stdout=b'different-size'))
    add('usage-wall-join',lambda a:a[1]['real_time'].update(seconds=1.5))
    add('usage-scripted-zero-provider',lambda a:a[3].update(provider_calls=False))
    add('usage-scripted-zero-provider',lambda a:a[1]['tokens'].update(total=1))
    add('usage-scripted-zero-provider',lambda a:a[1]['tokens'].update(input=None,output=None,total=None,status='not_recorded'))
    return rows


class ScriptedUsage(unittest.TestCase):
    def test_measured_server_and_replays_are_separate(self):
        value=usage.scripted(*example());self.assertEqual(value['server_process_wall_seconds'],1.25)
        self.assertEqual(value['replay_process_wall_seconds'],[2.5,0]);self.assertEqual(value['model_calls'],0)
        self.assertEqual(value['tokens'],{'input':0,'output':0,'total':0})
        self.assertNotIn('agent_wall_time',value)
        self.assertEqual(value['replay_stream_counts'][0]['stdout_bytes'],5)
        self.assertIn('Not retained',value['replay_stdout_content_status'])

    def test_corruption_is_not_observed_usage(self):
        for gate,args in corruptions():
            with self.subTest(gate=gate),self.assertRaisesRegex(AssessmentInputError,gate):usage.scripted(*args)

    def test_zero_wall_is_a_valid_measurement(self):
        a=example();a[1]['real_time']['seconds']=a[2][0]['wall_seconds']=0
        self.assertEqual(usage.scripted(*a)['server_process_wall_seconds'],0)

if __name__=='__main__':unittest.main()
