"""MCP stdio adapter. Host paths and trusted state are never subject arguments."""
import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from .backends import load_manifest
from .codec import canonical, digest
from .game import Game

MAX_REQUEST_BYTES=65536
MAX_FINISH_SUMMARY_BYTES=16384
MAX_FINISH_RESPONSE_BYTES=1024*1024
FINISH_RECORD_NAME='finish-record.json'


def finish_summary(record):
    """Public finish result; the full scored record remains a host artifact."""
    score=record.get('score')
    if (record.get('finished') is not True or type(score) is not dict
            or score.get('schema')!='hgj/repair-score/v1'
            or score.get('status')!='scored' or record.get('scoring_status')!='scored'
            or record.get('score_sha256')!=digest(score)
            or type(record.get('actions')) is not list or not record['actions']
            or type(score.get('tool_calls')) is not int or score['tool_calls']!=len(record['actions'])
            or any(type(row.get('result',{}).get('ok')) is not bool for row in record['actions'])
            or record['actions'][-1]['name']!='finish'
            or record['actions'][-1]['result'].get('ok') is not True
            or canonical(record['actions'][-1]['result'].get('score'))!=canonical(score)):
        raise ValueError('Compact finish requires the committed scored finish')
    summary={key:score[key] for key in ('schema','status','tool_calls')}
    for key in ('bolt_accuracy','checklist_accuracy'):
        summary[key]={field:score[key][field] for field in ('correct','total','accuracy_percent')}
    summary['human_time']={field:score['human_time'][field] for field in
        ('productive_seconds','penalty_seconds','total_seconds','reference_seconds')}
    summary['mistakes']={field:score['mistakes'][field] for field in ('count','by_type')}
    if 'primary_score' in score:
        summary['primary_score']={field:score['primary_score'][field] for field in
            ('schema','points_earned','total_points','S_full','S_partial')}
    value={'ok':True,'schema':'hgj/finish-summary/v1',
           'scoring_status':record['scoring_status'],'score_summary':summary,
           'record':{'file':FINISH_RECORD_NAME,'sha256':digest(record),
                     'bytes':len(canonical(record))}}
    if 'turns_remaining' in record['actions'][-1]['result']:
        value['turns_remaining']=record['actions'][-1]['result']['turns_remaining']
    if len(canonical(value))>MAX_FINISH_SUMMARY_BYTES:
        raise ValueError('Compact finish summary exceeds transport limit')
    return copy.deepcopy(value)


def request_lines(stream):
    """Bound allocation before parsing; drain one oversized frame at a time."""
    while True:
        line=stream.readline(MAX_REQUEST_BYTES+1)
        if not line:return
        if len(line)>MAX_REQUEST_BYTES:
            while line and not line.endswith('\n'):
                line=stream.readline(MAX_REQUEST_BYTES+1)
            yield None
        else:
            yield line


def atomic_bytes(path, data):
    temp=path.with_name(path.name+'.tmp')
    with open(temp,'wb') as f: os.chmod(temp,0o600); f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(temp,path)


def atomic(path, value):
    atomic_bytes(path, canonical(value))


def serve(game, stream, sink, out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    journal=out/'actions.jsonl'; final=out/'run.json'
    if any((out/name).exists() for name in ('actions.jsonl','run.json','report.json',FINISH_RECORD_NAME)):
        raise FileExistsError('Refuse existing run output')
    initialized=False; initialize_received=False; prior_seq=0
    started = time.monotonic()
    committed = game.export()
    termination = 'input_ended_without_finish'
    try:
        with open(journal,'xb') as log:
            os.chmod(journal,0o600)
            def send(value, *, compact_finish=False):
                raw=canonical(value)
                if compact_finish and len(raw)>MAX_FINISH_RESPONSE_BYTES:
                    raise ValueError('Compact finish response exceeds transport limit')
                sink.write(raw.decode()); sink.flush()
            for line in request_lines(stream):
                request=None; request_id=None
                compact_finish=False
                try:
                    if line is None or len(line.encode('utf-8'))>MAX_REQUEST_BYTES:
                        raise ValueError('Request exceeds transport limit')
                    request=json.loads(line)
                    # Validate serializability before dispatch: invalid Unicode and
                    # nonfinite numbers must never contaminate the action journal.
                    canonical(request)
                    if not isinstance(request,dict) or request.get('jsonrpc')!='2.0' or not isinstance(request.get('method'),str):
                        raise ValueError('Invalid JSON-RPC request')
                    if 'id' not in request:
                        if request['method']=='notifications/initialized' and initialize_received:
                            initialized=True
                        continue
                    if type(request['id']) not in (int,str): raise ValueError('Invalid request ID')
                    request_id=request['id']
                    method=request['method']; params=request.get('params',{})
                    if method=='initialize':
                        if not isinstance(params,dict) or not isinstance(params.get('protocolVersion'),str): raise ValueError('Missing protocol version')
                        initialized=False; initialize_received=True
                        result={'protocolVersion':'2025-11-25','capabilities':{'tools':{'listChanged':False}},
                                'serverInfo':{'name':'headgasket','version':'0.1.0'}}
                    elif method=='ping': result={}
                    elif method=='tools/list': result={'tools':game.tools()}
                    elif method=='tools/call':
                        if not initialized: raise ValueError('Client is not initialized')
                        if not isinstance(params,dict) or not isinstance(params.get('name'),str): raise ValueError('Invalid tool name')
                        value=game.call(params['name'],params.get('arguments',{}))
                        exported = game.export()
                        atomic(final, exported)
                        committed = exported
                        log.write(canonical(game.records[-1])); log.flush(); os.fsync(log.fileno()); prior_seq+=1
                        if game.procedure_scoring:
                            from .repair_report import report_for_run
                            atomic(out/'report.json', report_for_run(committed, time.monotonic()-started,
                                terminal_reason='finished' if committed['finished'] else terminal_reason(committed, 'running')))
                            if params['name']=='finish' and value['ok'] is True:
                                compact=finish_summary(committed)
                                atomic(out/FINISH_RECORD_NAME, committed)
                                value=compact
                                compact_finish=True
                        result={'content':[{'type':'text','text':canonical(value).decode().strip()}],'isError':not value['ok']}
                    else:
                        send({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':'Method unavailable'}}); continue
                    send({'jsonrpc':'2.0','id':request['id'],'result':result},compact_finish=compact_finish)
                except (ValueError,TypeError,KeyError,RecursionError):
                    send({'jsonrpc':'2.0','id':request_id,
                          'error':{'code':-32602,'message':'Invalid request'}})
    except BaseException as error:
        termination = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'transport_error'
        raise
    finally:
        # A signal may interrupt a tool or output write. Only the last committed
        # export is authoritative; an in-flight mutable Game is never exported.
        atomic(final, committed)
        atomic_bytes(journal, b''.join(canonical(row) for row in committed['actions']))
        if game.procedure_scoring:
            from .repair_report import report_for_run
            reason = 'finished' if committed['finished'] else terminal_reason(committed, termination)
            atomic(out/'report.json', report_for_run(committed, time.monotonic()-started, terminal_reason=reason))
    return {'actions':len(committed['actions']),'finished':committed['finished']}


def terminal_reason(record, fallback='input_ended_without_finish'):
    if record.get('budget', {}).get('exhausted'):
        return 'budget_exhausted'
    if len(record['actions']) >= record['config']['factors']['tool_call_limit']:
        return 'tool_call_limit'
    return fallback


def run_manifest(manifest,out,source_runtime,manifest_sha256=None):
    if source_runtime is not globals().get('__loader__') or not hasattr(source_runtime,'require_module'):
        raise ValueError('Source-bound runtime context is required before manifest loading')
    source_runtime.require_module(__name__,globals());source_runtime.require_deployment()
    config,joint,soak=load_manifest(manifest,expected_sha256=manifest_sha256)
    return serve(Game(config,joint=joint,soak=soak,source_runtime=source_runtime),sys.stdin,sys.stdout,out)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest',required=True); p.add_argument('--out',required=True)
    a=p.parse_args()
    run_manifest(a.manifest,a.out,None)


if __name__=='__main__':
    try: main()
    except Exception as error:
        print('Head-gasket server stopped: '+type(error).__name__,file=sys.stderr); raise SystemExit(1)
