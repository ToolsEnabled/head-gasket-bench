"""Value checks for the procedure stdio delivery verifier; authored data only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hgj.codec import canonical, digest
from tools import repair_demo as demo


def case():
    # Authored under the hardened finish contract: the finish reply is the compact
    # summary (hgj/finish-summary/v1) of a committed scored record.
    score = {'schema':'hgj/repair-score/v1','status':'scored','tool_calls':1,
             'checklist_accuracy':{'correct':1,'total':1,'accuracy_percent':100},
             'bolt_accuracy':{'correct':1,'total':1,'accuracy_percent':100},'mistakes':{'count':0,'by_type':{}},
             'human_time':{'productive_seconds':1,'penalty_seconds':0,'total_seconds':1,'reference_seconds':1}}
    record = {'config':{'trusted_value':1},'finished':True,'scoring_status':'scored','score':score,
              'actions':[{'seq':1,'name':'finish','input':{},'result':{'ok':True,'score':copy.deepcopy(score)}}],
              'final_state':{'complete':True}}
    rows = demo.requests([{'name':'finish','input':{}}])
    return pack(record,rows)


def pack(record, rows=None):
    rows = rows or demo.requests([{'name':'finish','input':{}}])
    record['score_sha256'] = digest(record['score'])
    record['final_state_sha256'] = digest(record['final_state'])
    record['actions'][-1]['result']['score'] = copy.deepcopy(record['score'])
    from hgj.mcp import finish_summary
    replies = [{'jsonrpc':'2.0','id':0,'result':{}},{'jsonrpc':'2.0','id':1,'result':{}},
               {'jsonrpc':'2.0','id':2,'result':{'isError':False,'content':[{'type':'text','text':canonical(finish_summary(record)).decode()}]}}]
    return ['correct',copy.deepcopy(record['config']),rows,replies,record,
            b''.join(canonical(row) for row in record['actions']),[canonical(record),canonical(record)]]


def invalid(gate):
    values = case()
    record = values[4]
    if gate == 'config': values[1]['trusted_value'] = 2
    elif gate == 'finished':
        record['finished'] = False; values = pack(record)
    elif gate == 'journal': values[5] += b'\n'
    elif gate == 'reply_count': values[3].append({'jsonrpc':'2.0','id':999})
    elif gate == 'reply_identity': values[3][0]['id'] = False
    elif gate == 'requests': values[2][-1]['params']['arguments'] = {'extra':True}
    elif gate == 'successful_calls': values[3][-1]['result']['isError'] = True
    elif gate == 'reply_values': values[3][-1]['result']['content'][0]['text'] = '{"ok":false}'
    elif gate == 'replays': values[6][1] = b'changed'
    elif gate == 'output_hashes':
        record['final_state_sha256'] = '0'*64; values[6] = [canonical(record)]*2
    elif gate == 'finish_score':
        record['actions'][-1]['result']['score']['human_time']['total_seconds'] = 9
        values[3][-1]['result']['content'][0]['text'] = canonical(record['actions'][-1]['result']).decode()
        values[5] = b''.join(canonical(row) for row in record['actions'])
        values[6] = [canonical(record)]*2
    elif gate == 'correct_baseline':
        record['score']['bolt_accuracy']['accuracy_percent'] = 99; values = pack(record)
    elif gate == 'bad_control': values[0] = 'under_torque'
    elif gate == 'time_sum':
        record['score']['human_time']['total_seconds'] = 2; values = pack(record)
    else: raise AssertionError('Unknown authored output mutation')
    return values


OUTPUT_GATES = ('config','finished','journal','reply_count','reply_identity','requests',
                'successful_calls','reply_values','replays','output_hashes','finish_score',
                'correct_baseline','bad_control','time_sum')


def exercise(gate):
    if gate in OUTPUT_GATES:
        return demo.verify_case(*invalid(gate))
    if gate == 'procedure_mode':
        return demo.procedure_config({'repair_scoring':{'mode':'other'}})
    if gate == 'replay_config':
        return demo.replay_configuration({'config':{'value':False}}, {'value':0})
    if gate == 'process_exit':
        return demo.check_process(1)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'input.json'
        path.write_bytes(canonical({'value':'bounded synthetic input'}))
        if gate == 'document_pin':
            return demo.document(path,'0'*64)
        if gate == 'document_bound':
            # A valid JSON prefix plus whitespace isolates the byte bound from parsing.
            path.write_bytes(b'{}'+b' '*30)
            with patch.object(demo,'MAX_BYTES',16):
                return demo.document(path)
    raise AssertionError('Unknown authored input mutation')


class DeliveryTests(unittest.TestCase):
    def test_valid_joined_output(self):
        values = case()
        self.assertEqual(demo.verify_case(*values)['checklist_accuracy']['accuracy_percent'],100)

    def test_each_damaged_output_is_rejected(self):
        for gate in OUTPUT_GATES:
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                exercise(gate)

    def test_input_and_process_values_rejected(self):
        for gate in ('document_pin','document_bound','procedure_mode','replay_config','process_exit'):
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                exercise(gate)

    def test_valid_input_and_exit_values(self):
        demo.procedure_config({'repair_scoring':{'mode':'procedure-accuracy-v1'}})
        demo.check_process(0)
        demo.replay_configuration({'config':{'value':3}}, {'value':3})


if __name__ == '__main__':
    unittest.main()
