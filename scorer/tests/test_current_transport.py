"""Complete tiny authored transcripts, replay identity and typed message IDs."""
from copy import deepcopy
import json
import unittest
from job_accuracy import transport as t
from job_accuracy.independent import encoded,fingerprint,AssessmentInputError


def example():
    config={'scope':'authored transport fixture'}
    source={'sources':{'module':{'path':'module.py','sha256':'a'*64}},'bootstrap':{'path':'bootstrap.py','sha256':'b'*64}}
    source_raw=encoded(source);identity={'schema':'hgj/environment-source-identity/v1',
        'source_manifest_sha256':t.sha(source_raw),'source_manifest_body_sha256':fingerprint(source),
        'sources':source['sources'],'bootstrap':source['bootstrap']}
    a={'name':'look','input':{},'result':{'ok':False,'refusal':'Authored refused attempt'},'seq':1}
    r={'config':config,'config_sha256':fingerprint(config),'final_state':{},'final_state_sha256':fingerprint({}),
       'score':{},'score_sha256':fingerprint({}),'environment_source':identity,
       'environment_source_sha256':fingerprint(identity),'actions':[a]}
    asks=[{'jsonrpc':'2.0','id':0,'method':'initialize'}, {'jsonrpc':'2.0','method':'notifications/initialized'},
          {'jsonrpc':'2.0','id':1,'method':'tools/list'},
          {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':a['name'],'arguments':a['input']}}]
    replies=[{'jsonrpc':'2.0','id':0,'result':{}},{'jsonrpc':'2.0','id':1,'result':{}},
             {'jsonrpc':'2.0','id':2,'result':{'isError':False,'content':[{'type':'text','text':encoded(a['result']).decode()}]}}]
    raw=encoded(r)
    return [r,raw,t.sha(raw),config,source_raw,encoded(a),[raw,raw],b''.join(map(encoded,asks)),b''.join(map(encoded,replies))]


def edit_response(a,change):
    rows=[json.loads(r) for r in a[8].splitlines()];change(rows);a[8]=b''.join(map(encoded,rows))


def corruptions():
    rows=[]
    def add(gate,change):
        a=example();change(a);rows.append((gate,a))
    add('transport-record-pin',lambda a:a.__setitem__(2,'0'*64))
    add('transport-exact-replays',lambda a:a[6].__setitem__(1,a[6][1]+b' '))
    add('transport-record-values',lambda a:a.__setitem__(3,{'scope':'other'}))
    def changed_source(a):
        source=json.loads(a[4]);source['bootstrap']['sha256']='c'*64;a[4]=encoded(source)
    add('transport-source-identity',changed_source)
    add('transport-journal-bytes',lambda a:a.__setitem__(5,a[5]+b' '))
    add('transport-message-census',lambda a:a.__setitem__(7,a[7]+encoded({'jsonrpc':'2.0','method':'notifications/initialized'})))
    add('transport-message-identities',lambda a:edit_response(a,lambda rows:rows[0].update(id=False)))
    add('transport-message-identities',lambda a:edit_response(a,lambda rows:rows[2].update(id=1)))
    def handshake(a):
        def change(rows):rows[0].pop('result');rows[0]['error']={'code':-1}
        edit_response(a,change)
    add('transport-handshake-results',handshake)
    # The isError flag is part of the call envelope since the compact-finish
    # receiving change; the envelope gate refuses it before the value gate.
    add('transport-call-envelope',lambda a:edit_response(a,lambda rows:rows[2]['result'].update(isError=0)))
    add('transport-call-values',lambda a:edit_response(a,lambda rows:rows[2]['result']['content'][0].update(text='{"ok":true}')))
    return rows


class CurrentTransport(unittest.TestCase):
    def test_refused_action_is_valid_transport_data(self):
        r=t.verify(*example());self.assertEqual(r['actions'],1);self.assertEqual(r['full_raw_replay_pairs'],2)

    def test_corruptions_refuse_specific_boundary(self):
        for name,args in corruptions():
            with self.subTest(name=name),self.assertRaisesRegex(AssessmentInputError,name):t.verify(*args)

    def test_document_and_row_caps_are_declared_and_enforced(self):
        with self.assertRaisesRegex(AssessmentInputError,'transport-document-bound'):t.lines(b' '*(t.MAX_DOCUMENT_BYTES+1))
        with self.assertRaisesRegex(AssessmentInputError,'transport-transcript-bound'):t.lines(b'{}\n'*(t.MAX_TRANSCRIPT_ROWS+1))

    def test_malformed_protocol_has_named_refusal(self):
        a=example();a[8]=b'not-json'
        with self.assertRaisesRegex(AssessmentInputError,'transport-malformed'):t.verify(*a)

if __name__=='__main__':unittest.main()
