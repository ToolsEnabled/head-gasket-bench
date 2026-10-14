"""Receive an externally pinned thirteen-case saved batch; never run Game."""
import argparse,hashlib,json,re,time
from pathlib import Path,PurePosixPath
from job_accuracy import independent as core,checkpoints,transport,report,usage
from job_accuracy.checkpoint_contracts import ORIGINAL,AMENDMENT1,AMENDMENT2,selected_revision


def check_resources(root):
    """Refuse to start when the output filesystem has under 256 MiB free.

    The development lane imported a stricter machine-wide floor from a tool
    that is not part of this package; the receiving logic is unchanged.
    """
    import shutil
    if shutil.disk_usage(root).free < 256*1024*1024:
        raise RuntimeError('resource_floor_stop')

MAX_FILES=512
MAX_TOTAL=1024*1024*1024
MAX_FILE=transport.MAX_DOCUMENT_BYTES
ROLE_CONTRACT=Path(__file__).with_name('current_variant_source_roles.json')
CASES={(v,'correct','machine') for v in ('V1','V2','V3','V4','V5')}|{('V3','correct','replace')}|{
    ('V1','wrong_torque_sequence','machine'),('V1','under_torque','machine'),
    ('V1','skipped_final_stage','machine'),('V4','wrong_gasket','machine'),
    ('V2','reused_stretched_bolt','machine'),('V1','wrong_timing','machine'),
    ('V1','missing_attachment_restoration','machine')}
EXPECTED={'wrong_torque_sequence':(['CP09','CP10'],'wrong_order'),
          'under_torque':(['CP10'],'wrong_torque_value'),
          'skipped_final_stage':(['CP10'],'missing_torque_stage'),
          'wrong_gasket':(['CP08'],'wrong_gasket'),
          'reused_stretched_bolt':(['CP07'],'reused_stretched_bolt'),
          'wrong_timing':(['CP11'],'timing_marks_off'),
          'missing_attachment_restoration':(['CP12'],'missing_attachment_restore')}


def relative(name):
    p=PurePosixPath(name)
    core.check(type(name) is str and name and not p.is_absolute() and '..' not in p.parts
               and p.as_posix()==name and name!='.','batch-relative-path')
    return p


def read(root,name,pin,cap=MAX_FILE):
    p=root/relative(name)
    core.check(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'batch-file-location')
    with p.open('rb') as f:raw=f.read(cap+1)
    core.check(len(raw)<=cap and transport.sha(raw)==pin,'batch-file-pin-bound')
    return raw


def inventory(raw):
    rows=[r.split('  ',1) for r in raw.decode().splitlines()]
    core.check(0<len(rows)<=MAX_FILES and all(len(r)==2 for r in rows),'batch-inventory-shape')
    pins={}
    for pin,name in rows:
        relative(name)
        core.check(name not in pins and re.fullmatch('[0-9a-f]{64}',pin) is not None,'batch-inventory-unique')
        pins[name]=pin
    return pins


def catalogue(info):
    core.check(info.get('schema')=='hgj/variant-delivery/v1','batch-delivery-schema')
    rows=info['controls'];identities=[(r['variant'],r['control'],r['head_recovery']) for r in rows]
    core.check(len(rows)==13 and set(identities)==CASES and len({r['name'] for r in rows})==13,'batch-case-census')
    for row in rows:relative(row['name']);core.check(len(PurePosixPath(row['name']).parts)==1,'batch-case-name')
    core.check(type(info['server_processes']) is int and info['server_processes']==13
               and type(info['fresh_replay_processes']) is int and info['fresh_replay_processes']==26,
               'batch-process-census')
    return rows


def source_catalogue(info):
    sources=info['source_files']
    core.check(type(sources) is dict and 0<len(sources)<=128,'batch-source-census')
    for name,pin in sources.items():
        relative(name);core.check(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin) is not None,'batch-source-pin-shape')
    return sources


def source_roles(info,manifest,roles):
    expected=set(roles['runtime_modules'].values())|{roles['bootstrap']}|set(roles['supporting_files'])
    core.check(set(info['source_files'])==expected,'batch-complete-source-roles')
    core.check(set(manifest['sources'])==set(roles['runtime_modules'])
               and all(manifest['sources'][name].get('path')==path for name,path in roles['runtime_modules'].items()),
               'batch-runtime-module-roles')
    core.check(manifest['bootstrap'].get('path')==roles['bootstrap'],'batch-bootstrap-role')
    return {'runtime_modules':len(roles['runtime_modules']),'bootstrap_files':1,
            'supporting_files':len(roles['supporting_files']),'total_files':len(expected)}


def acceptance(control,assessment):
    primary=assessment['primary_score'];by_id={r['id']:r for r in primary['checkpoints']}
    if control=='correct':
        return primary['S_full']==1 and primary['points_earned']==18 and assessment['bolt_accuracy']['correct']==60 and assessment['mistakes']['count']==0 and assessment['human_time']['penalty_seconds']==0
    ids,cause=EXPECTED[control]
    return primary['S_full']==0 and all(by_id[k]['passed'] is False for k in ids) and assessment['mistakes']['by_type'].get(cause,0)>0


def case_inputs(row, record, value):
    config=record['config'];factors=config['factors']
    core.check(config['variant_id']==row['variant'],'batch-variant-binding')
    core.check(value['initial_evidence'].get('available') is True
               and value['initial_evidence'].get('budget_checked') is True
               and type(factors.get('turn_budget')) is int and factors['turn_budget']==1024
               and factors.get('turn_budget_unit')=='job-tool-action-attempts','batch-current-start')
    parts={p['id']:p for p in config['geometry']['parts']}
    head_ids={p for p,d in parts.items() if core.effective_role(d)=='head'}
    recoveries={r['name'] for r in record['final_state']['action_history']
                if r['name'] in ('machine_head','replace') and r['input'].get('part_id') in head_ids}
    if row['variant']=='V3' and row['control']=='correct':
        core.check(recoveries=={'replace' if row['head_recovery']=='replace' else 'machine_head'},'batch-recovery-binding')
    return sorted(recoveries)


def shared_values_agree(result):
    comparison=result.get('producer_comparison',{})
    return comparison.get('status') in ('agreement','disagreement') and comparison.get('disagreements')==[]


def classification(results):
    expected=all(r['expected_control_behavior'] is True for r in results)
    agree=all(r['primary_comparison']['status']=='agreement' for r in results)
    shared=all(shared_values_agree(r) for r in results)
    accepted=len(results)==13 and expected and agree and shared
    return {'status':'ACCEPTED' if accepted else 'RECEIVED_WITH_DISAGREEMENTS','accepted':accepted,
            'all_expected_behaviors':expected,'primary_agreement':agree,
            'shared_secondary_agreement':shared}


def assess_case(record,checkpoint_revision=ORIGINAL):
    """Only the receiving host selects rules; delivered labels never select them."""
    selected_revision(checkpoint_revision)
    settings=record['config']['repair_scoring']
    return checkpoints.score(record,settings['reference'],settings['human_time_policy'],
                             terminal_reason='scripted_finish',checkpoint_revision=checkpoint_revision)


def summary(state):
    accepted=state.get('accepted') is True
    lines=['# Scripted repair comparison','',
           'All thirteen jobs satisfy the expected results and agree on the compared values.' if accepted
           else 'The complete thirteen-job comparison has not been accepted.',
           '', 'This comparison uses saved scripted jobs. No agent or environment was run by the independent checker.',
           '', '| Job | Points / 18 | Success | Score | Technician work / penalties (s) | Scripted server wall (s) | Checkpoints not met |',
           '|---|---:|---:|---:|---:|---:|---|']
    if state.get('checkpoint_revision')==AMENDMENT1:
        lines[4:4]=['Host-selected rules: Amendment 1. Each complete loosening pass may use either documented order; inspected, serviceable original-cover reuse with sealant is permitted.', '']
    if state.get('checkpoint_revision')==AMENDMENT2:
        lines[4:4]=['Host-selected rules: Amendment 2. One complete documented loosening order must be used consistently across all passes; inspected, serviceable original-cover reuse with sealant is permitted.', '']
    for row in state['cases']:
        time_value=row['human_time']
        lines.append('| '+str(row['name'])+' | '+str(row['points_earned'])+' | '+str(row['S_full'])+' | '+
            format(row['S_partial'],'.6g')+' | '+str(time_value['productive_seconds'])+' / '+str(time_value['penalty_seconds'])+
            ' | '+str(row['scripted_server_wall_seconds'])+' | '+(', '.join(row['failed_checkpoints']) or 'none')+' |')
    lines += ['', 'Completed comparisons: '+str(len(state['cases']))+'/13. Primary result agreement: '+
              str(state.get('primary_agreement','pending'))+'. Agreement on shared bolt, mistake and time fields: '+
              str(state.get('shared_secondary_agreement','pending'))+'.',
              '', 'Technician durations are cited analyst estimates, not measured repair times. Scripted server wall is measured separately from independent analysis time and is not agent wall time.',
              'Individual reports include all ten bolt results, mistakes, checklist scope and usage. Different checklist item sets are listed separately; unknown conditions do not earn an observed condition result.',
              'Zero model calls and tokens in completed case reports come from the joined scripted receipts. This is not evidence from a model subject.']
    if state.get('reason'):lines += ['', 'Comparison stopped: '+state['reason']+'.']
    return '\n'.join(lines)+'\n'


def main(root,pin,source_root,out,*,checkpoint_revision=ORIGINAL):
    selected_revision(checkpoint_revision)
    check_resources(Path.cwd());out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    results=[];state={'status':'RECEIVING','environment_executions':0,'cases':results,
                     'inventory_sha256':pin,'limits':{'files':MAX_FILES,'file_bytes':MAX_FILE,'total_bytes':MAX_TOTAL,'action_attempts':core.MAX_ACTIONS},
                     'scope':'Saved source files, transcripts and exact replays; thirteen new independent reductions, no producer execution',
                     'checkpoint_revision':checkpoint_revision,
                     'rule_selection':'Explicit host selection; delivery labels do not select the rule. External source/contract correspondence is a separate receiving prerequisite.'}
    def checkpoint():(out/'result.json').write_bytes(core.encoded(state))
    checkpoint()
    try:
        invraw=read(root,'SHA256SUMS',pin,256*1024);pins=inventory(invraw);(out/'DELIVERY-SHA256SUMS').write_bytes(invraw)
        consumed=[];total=0
        for name,h in pins.items():
            raw=read(root,name,h);total+=len(raw);core.check(total<=MAX_TOTAL,'batch-total-bound')
            consumed.append({'path':name,'sha256':h,'bytes':len(raw)})
        state.update(delivery_files=len(consumed),delivery_bytes=total)
        def payload(name):
            core.check(name in pins,'batch-listed-payload');return read(root,name,pins[name])
        info=json.loads(payload('report.json'));rows=catalogue(info);source_raw=payload('environment-source.json');source=json.loads(source_raw)
        core.check(source.get('schema')=='hgj/environment-source/v1','batch-source-schema')
        core.check(transport.sha(source_raw)==info['source_manifest_sha256'],'batch-source-manifest')
        roles=json.loads(ROLE_CONTRACT.read_bytes());role_counts=source_roles(info,source,roles)
        source_rows=[];source_bytes=0
        for name,h in source_catalogue(info).items():
            raw=read(source_root,name,h);source_bytes+=len(raw);core.check(source_bytes<=MAX_FILE,'batch-source-total')
            q=out/'environment-source'/relative(name);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
            source_rows.append({'path':name,'sha256':h,'bytes':len(raw)})
        for entry in [source['bootstrap'],*source['sources'].values()]:
            core.check(info['source_files'].get(entry['path'])==entry['sha256'],'batch-runtime-closure')
        (out/'SOURCE-RECEIPT.json').write_bytes(core.encoded({'source_files':source_rows,'delivery_files':consumed,'manifest_sha256':transport.sha(source_raw),
            'role_contract_sha256':transport.sha(ROLE_CONTRACT.read_bytes()),'role_counts':role_counts}))
        performance=json.loads(payload('performance.json'))
        expected_labels={row['name']+suffix for row in rows for suffix in ('','-replay-1','-replay-2')}
        core.check(type(performance) is list and len(performance)==39
                   and {r.get('label') for r in performance}==expected_labels,'batch-performance-census')
        for p in [Path(__file__),ROLE_CONTRACT,*Path('job_accuracy').glob('*.py')]:
            p=p.relative_to(Path.cwd()) if p.is_absolute() else p
            q=out/'independent-source'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
        for row in rows:
            check_resources(Path.cwd());label=row['name'];record_raw=payload(label+'/run.json');record=json.loads(record_raw)
            config=json.loads(payload(row['variant']+'.configuration.json'))
            joined=transport.verify(record,record_raw,row['run_sha256'],config,source_raw,payload(label+'/actions.jsonl'),
                [payload(label+'.replay-'+str(i)+'.json') for i in (1,2)],payload(label+'.requests.jsonl'),payload(label+'.responses.jsonl'),
                finish_record_raw=payload(label+'/finish-record.json') if label+'/finish-record.json' in pins else None)
            core.check(record['finished'] is True and record['scoring_status']=='scored','batch-finished-case')
            target=out/label;target.mkdir();values=[];walls=[]
            for i in range(2):
                before=time.monotonic();value=assess_case(record,checkpoint_revision)
                walls.append(time.monotonic()-before);data=core.encoded(value);core.check(len(data)<=MAX_FILE,'batch-assessment-bound');values.append(data)
                (target/('assessment-'+str(i)+'.json')).write_bytes(data)
            core.check(values[0]==values[1],'batch-assessment-replay')
            recovery_events=case_inputs(row,record,value)
            measured=usage.scripted(record,json.loads(payload(label+'/scripted-report.json')),performance,info,label,
                {'stdin':payload(label+'.requests.jsonl'),'stdout':payload(label+'.responses.jsonl'),'stderr':payload(label+'.stderr.txt')})
            envelope=report.run_report(value,tokens={k:measured['tokens'][k] for k in ('input','output')},
                token_source=measured['token_source'],model_calls=0,model_call_source='Pinned scripted delivery; no model calls',
                api_cost={'usd':0,'source':'Pinned scripted delivery; no provider calls'})
            envelope['scripted_usage']=measured
            (target/'REPORT.json').write_bytes(core.encoded(envelope));(target/'REPORT.md').write_text(report.summary(envelope)+
                '\nScripted server process wall: '+str(measured['server_process_wall_seconds'])+' s. '
                'This is a scripted process measurement; no agent ran.\n')
            results.append({'name':label,'variant':row['variant'],'control':row['control'],'head_recovery':row['head_recovery'],
                'observed_head_recovery_operations':recovery_events,
                'transport':joined,'expected_control_behavior':acceptance(row['control'],value),
                'points_earned':value['primary_score']['points_earned'],'S_full':value['primary_score']['S_full'],
                'S_partial':value['primary_score']['S_partial'],'failed_checkpoints':[r['id'] for r in value['primary_score']['checkpoints'] if not r['passed']],
                'primary_comparison':value['primary_comparison'],'producer_comparison':value['producer_comparison'],
                'mistakes':value['mistakes']['by_type'],'human_time':{k:value['human_time'][k] for k in ('productive_seconds','penalty_seconds','total_seconds')},
                'scripted_server_wall_seconds':measured['server_process_wall_seconds'],
                'initial_evidence':value['initial_evidence'],'analysis_wall_seconds':walls,'assessment_sha256':transport.sha(values[0])})
            checkpoint()
        state.update(classification(results))
    except (core.AssessmentInputError,KeyError,ValueError,TypeError,OSError) as error:
        state.update(status='REFUSED',reason=error.code if isinstance(error,core.AssessmentInputError) else type(error).__name__)
        raise
    finally:
        state['receiving_wall_seconds']=time.monotonic()-started;checkpoint()
        (out/'REPORT.md').write_text(summary(state))
    print({k:state[k] for k in ('status','all_expected_behaviors','primary_agreement','receiving_wall_seconds')})
    if not state['accepted']:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--delivery',type=Path,required=True);p.add_argument('--inventory-sha256',required=True)
    p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--checkpoint-revision',choices=(ORIGINAL,AMENDMENT1,AMENDMENT2),default=ORIGINAL);a=p.parse_args()
    main(a.delivery,a.inventory_sha256,a.source_root,a.out,checkpoint_revision=a.checkpoint_revision)
