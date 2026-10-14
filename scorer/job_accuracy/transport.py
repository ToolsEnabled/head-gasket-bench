"""Join saved MCP bytes and their offered source manifest without execution."""
import hashlib
import json
from .independent import check, encoded, equal, fingerprint, MAX_ACTIONS, AssessmentInputError

MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
MAX_TRANSCRIPT_ROWS = MAX_ACTIONS + 3


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def lines(raw):
    check(type(raw) is bytes and len(raw) <= MAX_DOCUMENT_BYTES, 'transport-document-bound')
    rows=raw.splitlines()
    check(len(rows)<=MAX_TRANSCRIPT_ROWS and all(len(r)<=MAX_DOCUMENT_BYTES for r in rows), 'transport-transcript-bound')
    return [json.loads(r) for r in rows]


def verify(*args, **kwargs):
    try:
        return _verify(*args, **kwargs)
    except AssessmentInputError:
        raise
    except (KeyError, TypeError, ValueError, IndexError):
        raise AssessmentInputError('transport-malformed') from None


def compact_finish(record, action, value, snapshot):
    """Check the compact wire projection against its pinned full disk record."""
    check(type(snapshot) is bytes and len(snapshot)<=MAX_DOCUMENT_BYTES
          and snapshot==encoded(record),'transport-finish-snapshot')
    check(action is record['actions'][-1] and action['name']=='finish'
          and action['result'].get('ok') is True and record['finished'] is True
          and record['scoring_status']=='scored'
          and equal(action['result'].get('score'),record['score']), 'transport-finish-witness')
    score=record['score']
    projected={key:score[key] for key in ('schema','status','tool_calls')}
    for key in ('bolt_accuracy','checklist_accuracy'):
        projected[key]={field:score[key][field] for field in ('correct','total','accuracy_percent')}
    projected['human_time']={field:score['human_time'][field] for field in
        ('productive_seconds','penalty_seconds','total_seconds','reference_seconds')}
    projected['mistakes']={field:score['mistakes'][field] for field in ('count','by_type')}
    if 'primary_score' in score:
        projected['primary_score']={field:score['primary_score'][field] for field in
            ('schema','points_earned','total_points','S_full','S_partial')}
    expected={'ok':True,'schema':'hgj/finish-summary/v1','scoring_status':'scored',
              'score_summary':projected,
              'record':{'file':'finish-record.json','sha256':sha(snapshot),'bytes':len(snapshot)}}
    if 'turns_remaining' in action['result']:
        expected['turns_remaining']=action['result']['turns_remaining']
    check(equal(value,expected),'transport-finish-projection')


def _verify(record, run_raw, raw_pin, config, source_raw, journal, replays, requests_raw, responses_raw, *, finish_record_raw=None):
    """External packet receiving supplies raw_pin and authenticates source bytes.

    This verifies completed or incomplete recorded calls alike. Cohort acceptance
    separately requires finished scripted cases and their expected checkpoints.
    """
    check(type(run_raw) is bytes and len(run_raw)<=MAX_DOCUMENT_BYTES and sha(run_raw)==raw_pin
          and equal(json.loads(run_raw),record),'transport-record-pin')
    check(len(replays)==2 and all(type(raw) is bytes and raw==run_raw for raw in replays), 'transport-exact-replays')
    check(equal(record['config'],config) and record['config_sha256']==fingerprint(config)
          and record['final_state_sha256']==fingerprint(record['final_state'])
          and record['score_sha256']==fingerprint(record['score']), 'transport-record-values')
    source=json.loads(source_raw);identity=record['environment_source']
    check(identity['schema']=='hgj/environment-source-identity/v1'
          and identity['source_manifest_sha256']==sha(source_raw)
          and identity['source_manifest_body_sha256']==fingerprint(source)
          and equal(identity['sources'],source['sources']) and equal(identity['bootstrap'],source['bootstrap'])
          and record['environment_source_sha256']==fingerprint(identity), 'transport-source-identity')
    actions=record['actions']
    check(type(actions) is list and len(actions)<=MAX_ACTIONS
          and journal==b''.join(encoded(a) for a in actions), 'transport-journal-bytes')
    requests=lines(requests_raw);responses=lines(responses_raw)
    # This is the explicit scripted collector protocol, including initialization.
    expected=['initialize','notifications/initialized','tools/list']+['tools/call']*len(actions)
    check([r.get('method') for r in requests]==expected
          and len(responses)==len(actions)+2, 'transport-message-census')
    asks=[r for r in requests if 'id' in r]
    check(len(asks)==len(responses) and all(type(r.get('id')) is int for r in asks+responses)
          and len({r['id'] for r in asks})==len(asks)
          and all(r.get('jsonrpc')=='2.0' for r in requests+responses)
          and [r['id'] for r in asks]==[r['id'] for r in responses], 'transport-message-identities')
    check(all('result' in r and 'error' not in r for r in responses[:2]), 'transport-handshake-results')
    compact_rows=[]
    for action,request,response in zip(actions,requests[3:],responses[2:]):
        reply=response.get('result',{});content=reply.get('content')
        check(equal(request.get('params'),{'name':action['name'],'arguments':action['input']})
              and 'error' not in response and reply.get('isError') is False
              and type(content) is list and len(content)==1 and content[0].get('type')=='text', 'transport-call-envelope')
        value=json.loads(content[0]['text'])
        if type(value) is dict and value.get('schema')=='hgj/finish-summary/v1':
            compact_finish(record,action,value,finish_record_raw)
            check(len(encoded(response))<=1024*1024,'transport-finish-wire-bound')
            compact_rows.append(len(encoded(response)))
        else:
            check(equal(value,action['result']),'transport-call-values')
    check(finish_record_raw is None or len(compact_rows)==1,'transport-finish-census')
    return {'actions':len(actions),'requests':len(requests),'responses':len(responses),
            'full_raw_replay_pairs':2,'run_raw_sha256':raw_pin,'source_manifest_raw_sha256':sha(source_raw),
            'compact_finish_snapshots':len(compact_rows),'compact_finish_wire_bytes':compact_rows,
            'scope':'Retained byte and value joins; source file bytes and process receipts require separate receiving'}
