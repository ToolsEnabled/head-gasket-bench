"""Run five tasks, two head recovery routes and seven bad jobs through MCP."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time
from hgj.codec import canonical,digest
from tools.freeze_environment_source import snapshot
from tools.source_server import SourceRuntime
from tools.repair_demo import requests,verify_case,require,check_process,sha,write,procedure_config,replay_configuration

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=64*1024*1024
PROCESS_TIMEOUT_SECONDS=900
CASES=[(v,'correct','machine') for v in ('V1','V2','V3','V4','V5')]+[('V3','correct','replace')]+[
    ('V1','wrong_torque_sequence','machine'),('V1','under_torque','machine'),
    ('V1','skipped_final_stage','machine'),('V4','wrong_gasket','machine'),
    ('V2','reused_stretched_bolt','machine'),('V1','wrong_timing','machine'),
    ('V1','missing_attachment_restoration','machine')]



EXPECTED_CHECKPOINTS={
    'wrong_torque_sequence':('CP09','CP10'), 'under_torque':('CP10',),
    'skipped_final_stage':('CP10',), 'wrong_gasket':('CP08',),
    'reused_stretched_bolt':('CP07',), 'wrong_timing':('CP11',),
    'missing_attachment_restoration':('CP12',),
}


def verify_primary(name,score):
    primary=score.get('primary_score',{})
    rows=primary.get('checkpoints',[])
    weights=(1,2,1,1,1,1,1,2,2,2,2,2)
    require(primary.get('schema')=='hgj/repair-checkpoints/v1' and len(rows)==12
            and all(row.get('id')=='CP'+str(i+1).zfill(2)
            and type(row.get('weight')) is int and row['weight']==weights[i]
            and type(row.get('passed')) is bool for i,row in enumerate(rows)),
            'primary_schema')
    earned=sum(r['weight'] for r in rows if r['passed'])
    full=int(all(r['passed'] for r in rows))
    require(type(primary.get('points_earned')) is int and primary['points_earned']==earned
            and type(primary.get('total_points')) is int and primary['total_points']==18
            and type(primary.get('S_full')) is int and primary['S_full']==full
            and type(primary.get('S_partial')) in (int,float)
            and primary['S_partial']==0.5*(earned/18)+0.5*full,'primary_formula')
    by_id={r['id']:r for r in rows}
    require((earned==18 and full==1) if name=='correct' else
            (full==0 and all(by_id[key]['passed'] is False for key in EXPECTED_CHECKPOINTS[name])),
            'primary_expected')
    return primary


def document(path,pin=None):
    with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    require(len(raw)<=MAX_BYTES,'document_bound')
    require(pin is None or sha(raw)==pin,'document_pin')
    return json.loads(raw)


def worker(args):
    config=document(args.config,args.config_pin);procedure_config(config)
    runtime=SourceRuntime(ROOT,args.source,args.source_pin)
    with runtime.active():
        game=importlib.import_module('hgj.game')
        if args.worker=='serve':
            importlib.import_module('hgj.mcp').serve(game.Game(config,source_runtime=runtime),
                                                    sys.stdin,sys.stdout,args.out)
        else:
            record=document(args.record);replay_configuration(record,config)
            write(args.out,canonical(game.replay(record,source_runtime=runtime)))


def run(out,removal_source):
    from tools.variant_controls import configuration,actions_for_variant
    from hgj.repair_report import report_for_run
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    source_raw=canonical(snapshot(ROOT));source_path=out/'environment-source.json';write(source_path,source_raw)
    configs={}
    for variant in ('V1','V2','V3','V4','V5'):
        config=configuration(variant,with_removal_policy=True,removal_source_dir=removal_source)
        raw=canonical(config);path=out/(variant+'.configuration.json');write(path,raw)
        configs[variant]=(config,path,sha(raw))
    performance=[];summaries=[]
    def launch(mode,path,label,config_path,config_pin,incoming=b'',record=None):
        command=[sys.executable,'-B','-m','tools.variant_demo','--worker',mode,'--out',str(path),
                 '--config',str(config_path),'--config-pin',config_pin,
                 '--source',str(source_path),'--source-pin',sha(source_raw)]
        if record is not None:command+=['--record',str(record)]
        started=time.monotonic()
        try:
            result=subprocess.run(command,input=incoming,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  cwd=ROOT,timeout=PROCESS_TIMEOUT_SECONDS,check=False)
        except subprocess.TimeoutExpired as error:
            elapsed=time.monotonic()-started
            stdout,stderr=error.stdout or b'',error.stderr or b''
            write(out/(label+'.timeout-stdout.bin'),stdout)
            write(out/(label+'.timeout-stderr.bin'),stderr)
            performance.append({'label':label,'status':'child_timeout','exit_code':None,
                'wall_seconds':elapsed,'deadline_seconds':PROCESS_TIMEOUT_SECONDS,
                'stdin_bytes':len(incoming),'stdout_bytes':len(stdout),'stderr_bytes':len(stderr)})
            (out/'performance.json').write_bytes(canonical(performance))
            committed=Path(path)/'run.json'
            if mode=='serve' and committed.exists():
                partial=document(committed)
                envelope=report_for_run(partial,elapsed,tokens={'input':0,'output':0},
                    time_source='Scripted parent process monotonic clock through child timeout',
                    token_source='Zero provider calls in this scripted control',
                    terminal_reason='finished' if partial['finished'] is True else 'interrupted')
                envelope['collector_stop_reason']='child_timeout'
                write(out/(label+'.timeout-report.json'),canonical(envelope))
            raise
        row={'label':label,'wall_seconds':time.monotonic()-started,'exit_code':result.returncode,
             'stdin_bytes':len(incoming),'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr)}
        performance.append(row);(out/'performance.json').write_bytes(canonical(performance))
        write(out/(label+'.stderr.txt'),result.stderr);check_process(result.returncode)
        return result.stdout,row
    for variant,name,recovery in CASES:
        label=variant+'-'+name+('-replacement-head' if recovery=='replace' else '')
        config,path,pin=configs[variant]
        actions=actions_for_variant(config,name,head_recovery=recovery);rows=requests(actions)
        incoming=b''.join(canonical(row) for row in rows);write(out/(label+'.requests.jsonl'),incoming)
        raw,timing=launch('serve',out/label,label,path,pin,incoming);write(out/(label+'.responses.jsonl'),raw)
        record_path=out/label/'run.json';record=document(record_path);replays=[]
        require((out/label/'finish-record.json').read_bytes()==canonical(record),'finish_artifact')
        for index in (1,2):
            destination=out/(label+'.replay-'+str(index)+'.json')
            launch('replay',destination,label+'-replay-'+str(index),path,pin,record=record_path)
            replays.append(destination.read_bytes())
        score=verify_case(name,config,rows,[json.loads(line) for line in raw.splitlines()],record,
                          (out/label/'actions.jsonl').read_bytes(),replays)
        primary=verify_primary(name,score)
        report=report_for_run(record,timing['wall_seconds'],tokens={'input':0,'output':0},
            time_source='Scripted server process wall time; no agent provider',
            token_source='Zero model/provider calls in this scripted control')
        write(out/label/'scripted-report.json',canonical(report))
        row={'name':label,'variant':variant,'control':name,'head_recovery':recovery,
             'run_sha256':sha(record_path.read_bytes()),'score_sha256':record['score_sha256'],
             'final_state_sha256':record['final_state_sha256'],'tool_calls':len(record['actions']),
             'bolt_accuracy_percent':score['bolt_accuracy']['accuracy_percent'],
             'checklist_accuracy_percent':score['checklist_accuracy']['accuracy_percent'],
             'human_productive_seconds':score['human_time']['productive_seconds'],
             'human_penalty_seconds':score['human_time']['penalty_seconds'],
             'mistakes_by_type':score['mistakes']['by_type'],'exact_replays':2,
             'points_earned':primary['points_earned'],'S_full':primary['S_full'],'S_partial':primary['S_partial'],
             'failed_checkpoints':[r['id'] for r in primary['checkpoints'] if not r['passed']]}
        summaries.append(row);(out/'controls.json').write_bytes(canonical(summaries));print(json.dumps(row),flush=True)
    paths={row['path'] for row in json.loads(source_raw)['sources'].values()}
    paths.update(('tools/source_server.py','tools/freeze_environment_source.py','tools/variant_controls.py',
                  'tools/l1_controls.py','tools/variant_demo.py','tools/prepare_variant.py','tools/repair_demo.py',
                  'tools/repair_controls.py','hgj/fixtures.py','data/service.json','data/labor-v2.json',
                  'data/human-time-policy-v3.json','data/procedure-retained-bodies.json'))
    report={'schema':'hgj/variant-delivery/v1','controls':summaries,
            'source_manifest_sha256':sha(source_raw),'source_files':{p:sha((ROOT/p).read_bytes()) for p in sorted(paths)},
            'server_processes':len(CASES),'fresh_replay_processes':2*len(CASES),
            'provider_calls':0,'model_calls':0,'physical_acceptance':False,
            'scoring_scope':'Signed environment twelve-checkpoint score plus secondary accuracy; independent L2 agreement is received separately',
            'limits':{'child_timeout_seconds':PROCESS_TIMEOUT_SECONDS,'record_bytes':MAX_BYTES,
                      'stdout_stderr_byte_cap':None,'action_attempts':1024},
            'removal_policy_sha256':configs['V1'][0]['benchmark_removal']['policy_sha256'],
            'qualification':'L1 labelled benchmark removal rules; initial mechanical conditions, bench service results and labor durations remain stated estimates/stand-ins'}
    write(out/'report.json',canonical(report))
    members=sorted(path for path in out.rglob('*') if path.is_file())
    write(out/'SHA256SUMS',''.join(sha(path.read_bytes())+'  '+path.relative_to(out).as_posix()+'\n' for path in members).encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    parser.add_argument('--worker',choices=['serve','replay']);parser.add_argument('--removal-source')
    for name in ('config','config-pin','source','source-pin','record'):parser.add_argument('--'+name)
    args=parser.parse_args()
    if args.worker:worker(args)
    else:
        if args.removal_source is None:parser.error('--removal-source is required')
        run(args.out,args.removal_source)


if __name__=='__main__':main()
