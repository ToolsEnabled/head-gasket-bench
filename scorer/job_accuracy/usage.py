"""Join measured scripted process costs; never call them agent wall time."""
from .independent import check,equal,finite,fingerprint


def scripted(record, envelope, performance, delivery, label, streams):
    check(envelope.get('schema')=='hgj/repair-run-report/v1'
          and envelope.get('run_sha256')==fingerprint(record)
          and envelope.get('score_sha256')==record['score_sha256'],'usage-record-binding')
    score=record['score']
    check(all(equal(envelope.get(k),score.get(k)) for k in
              ('human_time','mistakes','bolt_accuracy','checklist_accuracy','coverage','reference_sha256','primary_score')),
          'usage-score-fields')
    actions=record['actions'];success=sum(a['result']['ok'] is True for a in actions)
    counts={'attempted':len(actions),'successful':success,'refused':len(actions)-success}
    check(record.get('finished') is True and any(a['name']=='finish' and a['result']['ok'] is True for a in actions)
          and all(type(a['result']['ok']) is bool for a in actions)
          and equal(envelope.get('tool_calls'),counts) and envelope.get('finished') is True
          and envelope.get('status')=='finished' and envelope.get('terminal_reason')=='finished',
          'usage-completion-counts')
    check(type(performance) is list and all(type(r) is dict and type(r.get('label')) is str for r in performance)
          and len({r['label'] for r in performance})==len(performance),'usage-performance-census')
    expected={name:next((r for r in performance if r['label']==name),None)
              for name in (label,label+'-replay-1',label+'-replay-2')}
    check(all(r is not None and type(r.get('exit_code')) is int and r['exit_code']==0
              and finite(r.get('wall_seconds')) and r['wall_seconds']>=0
              and all(type(r.get(k)) is int and r[k]>=0 for k in ('stdin_bytes','stdout_bytes','stderr_bytes'))
              for r in expected.values()),
          'usage-process-results')
    check(type(streams) is dict and set(streams)=={'stdin','stdout','stderr'}
          and all(type(value) is bytes and len(value)==expected[label][key+'_bytes'] for key,value in streams.items()),
          'usage-server-stream-bytes')
    clock=envelope['real_time'];tokens=envelope['tokens']
    check(finite(clock.get('seconds')) and clock['seconds']==expected[label]['wall_seconds']
          and type(clock.get('source')) is str and bool(clock['source'].strip()),'usage-wall-join')
    check(all(type(delivery.get(k)) is int and delivery[k]==0 for k in ('provider_calls','model_calls'))
          and all(type(tokens.get(k)) is int and tokens[k]==0 for k in ('input','output','total'))
          and tokens.get('status')=='recorded' and type(tokens.get('source')) is str and bool(tokens['source'].strip()),
          'usage-scripted-zero-provider')
    return {'server_process_wall_seconds':clock['seconds'],'server_process_wall_source':clock['source'],
            'replay_process_wall_seconds':[expected[label+'-replay-'+str(i)]['wall_seconds'] for i in (1,2)],
            'replay_stream_counts':[{'label':label+'-replay-'+str(i),**{key:expected[label+'-replay-'+str(i)][key]
                for key in ('stdin_bytes','stdout_bytes','stderr_bytes')}} for i in (1,2)],
            'replay_stdout_content_status':'Not retained by this producer; declared counts only',
            'model_calls':0,'provider_calls':0,'tokens':{k:tokens[k] for k in ('input','output','total')},
            'token_source':tokens['source'],'scope':'Scripted process measurements and zero provider use; agent wall time does not apply'}
