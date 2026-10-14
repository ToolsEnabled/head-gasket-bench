"""Run the seven procedure-accuracy scripts through real MCP stdio.

No joint, soak, engine model or agent provider is invoked. Geometry and initial
conditions in this demonstration are explicitly identified stand-ins.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from hgj.codec import canonical, digest
from tools.freeze_environment_source import snapshot
from tools.source_server import SourceRuntime

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8*1024*1024
PROCESS_TIMEOUT_SECONDS = 60


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    with Path(path).open('xb') as stream:
        stream.write(raw)


def document(path, pin=None):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES+1)
    require(len(raw) <= MAX_BYTES, 'document_bound')
    require(pin is None or sha(raw) == pin, 'document_pin')
    return json.loads(raw)


def requests(actions):
    rows = [
        {'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':1,'method':'tools/list'},
    ]
    rows.extend({'jsonrpc':'2.0','id':index+2,'method':'tools/call',
                 'params':{'name':row['name'],'arguments':row['input']}}
                for index,row in enumerate(actions))
    return rows


def worker(args):
    config = document(args.config, args.config_pin)
    procedure_config(config)
    runtime = SourceRuntime(ROOT, args.source, args.source_pin)
    with runtime.active():
        game = importlib.import_module('hgj.game')
        if args.worker == 'serve':
            mcp = importlib.import_module('hgj.mcp')
            mcp.serve(game.Game(config, source_runtime=runtime), sys.stdin, sys.stdout, args.out)
        else:
            record = document(args.record)
            replay_configuration(record, config)
            actual = game.replay(record, source_runtime=runtime)
            write(args.out, canonical(actual))


EXPECTED = {
    'wrong_torque_sequence':'wrong_order', 'under_torque':'wrong_torque_value',
    'skipped_final_stage':'missing_torque_stage', 'wrong_gasket':'wrong_gasket',
    'reused_stretched_bolt':'reused_stretched_bolt', 'wrong_timing':'timing_marks_off',
    'missing_attachment_restoration':'missing_attachment_restore',
}


def require(condition, gate):
    if not condition:
        raise ValueError('Procedure verification failed: '+gate)


def procedure_config(config):
    require(config.get('repair_scoring', {}).get('mode') == 'procedure-accuracy-v1', 'procedure_mode')


def replay_configuration(record, config):
    require(canonical(record['config']) == canonical(config), 'replay_config')


def check_process(exit_code):
    require(type(exit_code) is int and exit_code == 0, 'process_exit')


def verify_case(name, config, rows, replies, record, journal, replays):
    require(canonical(record['config']) == canonical(config), 'config')
    require(record['finished'] is True and record['score'].get('schema') == 'hgj/repair-score/v1', 'finished')
    require(journal == b''.join(canonical(row) for row in record['actions']), 'journal')
    expected_replies = [row for row in rows if 'id' in row]
    require(len(replies) == len(expected_replies), 'reply_count')
    require(all(row.get('jsonrpc') == '2.0' and canonical(row.get('id')) == canonical(request['id'])
                for row,request in zip(replies, expected_replies)), 'reply_identity')
    calls = [row['params'] for row in rows if row['method'] == 'tools/call']
    require(canonical(calls) == canonical([{'name':row['name'],'arguments':row['input']}
                                         for row in record['actions']]), 'requests')
    for row,reply in zip(record['actions'],replies[2:]):
        require('error' not in reply and reply['result']['isError'] is False
                and row['result']['ok'] is True, 'successful_calls')
        if row['name']=='finish':
            from hgj.mcp import finish_summary
            expected_reply=finish_summary(record)
        else:
            expected_reply=row['result']
        require(canonical(json.loads(reply['result']['content'][0]['text'])) == canonical(expected_reply),
                'reply_values')
    require(len(replays) == 2 and all(raw == canonical(record) for raw in replays), 'replays')
    require(digest(record['final_state']) == record['final_state_sha256']
            and digest(record['score']) == record['score_sha256'], 'output_hashes')
    score = record['score']
    require(record['actions'][-1]['name'] == 'finish'
            and canonical(record['actions'][-1]['result'].get('score')) == canonical(score), 'finish_score')
    accuracy = score['checklist_accuracy']['accuracy_percent']
    if name == 'correct':
        require(accuracy == 100 and score['bolt_accuracy']['accuracy_percent'] == 100
                and score['mistakes']['count'] == 0 and score['human_time']['penalty_seconds'] == 0,
                'correct_baseline')
    else:
        require(accuracy < 100 and score['mistakes']['by_type'].get(EXPECTED[name],0) >= 1
                and score['human_time']['penalty_seconds'] > 0, 'bad_control')
    require(score['human_time']['total_seconds'] ==
            score['human_time']['productive_seconds'] + score['human_time']['penalty_seconds'], 'time_sum')
    return score


def run(out):
    from tools.repair_controls import example_config, actions_for, CONTROLS
    from hgj.repair_report import report_for_run
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = example_config()
    config_raw = canonical(config)
    config_path = out/'configuration.json'
    write(config_path, config_raw)
    source_raw = canonical(snapshot(ROOT))
    source_path = out/'environment-source.json'
    write(source_path, source_raw)
    performance, summaries = [], []
    def launch(mode, destination, label, incoming=b'', record=None):
        command = [sys.executable,'-B','-m','tools.repair_demo','--worker',mode,
                   '--out',str(destination),'--config',str(config_path),'--config-pin',sha(config_raw),
                   '--source',str(source_path),'--source-pin',sha(source_raw)]
        if record is not None:
            command += ['--record',str(record)]
        started = time.monotonic()
        completed = subprocess.run(command,input=incoming,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                   cwd=ROOT,timeout=PROCESS_TIMEOUT_SECONDS,check=False)
        observed = {'label':label,'wall_seconds':time.monotonic()-started,'exit_code':completed.returncode,
                    'stdin_bytes':len(incoming),'stdout_bytes':len(completed.stdout),'stderr_bytes':len(completed.stderr)}
        performance.append(observed)
        (out/'performance.json').write_bytes(canonical(performance))
        write(out/(label+'.stderr.txt'),completed.stderr)
        check_process(completed.returncode)
        return completed.stdout, observed
    for name in CONTROLS:
        rows = requests(actions_for(config,name))
        incoming = b''.join(canonical(row) for row in rows)
        write(out/(name+'.requests.jsonl'),incoming)
        raw, timing = launch('serve',out/name,name,incoming)
        write(out/(name+'.responses.jsonl'),raw)
        record_path = out/name/'run.json'
        record = document(record_path)
        require((out/name/'finish-record.json').read_bytes()==canonical(record),'finish_artifact')
        replays = []
        for index in (1,2):
            destination = out/(name+'.replay-'+str(index)+'.json')
            launch('replay',destination,name+'-replay-'+str(index),record=record_path)
            replays.append(destination.read_bytes())
        score = verify_case(name,config,rows,[json.loads(line) for line in raw.splitlines()],
                            record,(out/name/'actions.jsonl').read_bytes(),replays)
        report = report_for_run(record,timing['wall_seconds'],tokens={'input':0,'output':0},
            time_source='Measured scripted server subprocess wall time; no agent provider was invoked',
            token_source='Scripted control harness: zero provider calls and zero model tokens')
        write(out/name/'scripted-report.json',canonical(report))
        summaries.append({'name':name,'run_sha256':sha(record_path.read_bytes()),
            'score_sha256':record['score_sha256'],'final_state_sha256':record['final_state_sha256'],
            'tool_calls':len(record['actions']),'bolt_accuracy_percent':score['bolt_accuracy']['accuracy_percent'],
            'checklist_accuracy_percent':score['checklist_accuracy']['accuracy_percent'],
            'human_productive_seconds':score['human_time']['productive_seconds'],
            'human_penalty_seconds':score['human_time']['penalty_seconds'],
            'mistakes_by_type':score['mistakes']['by_type'],'exact_replays':2})
        print(json.dumps(summaries[-1],sort_keys=True),flush=True)
    selected = set(row['path'] for row in json.loads(source_raw)['sources'].values())
    selected.update(['tools/source_server.py','tools/freeze_environment_source.py','tools/repair_controls.py',
                     'tools/repair_demo.py','hgj/fixtures.py','data/service.json','data/labor.json',
                     'data/procedure-retained-bodies.json','data/human-time-policy.json'])
    report = {'schema':'hgj/procedure-control-delivery/v1','controls':summaries,
        'source_manifest_sha256':sha(source_raw),'config_sha256':sha(config_raw),
        'source_files':{path:sha((ROOT/path).read_bytes()) for path in sorted(selected)},
        'server_processes':7,'fresh_replay_processes':14,'provider_calls':0,'model_calls':0,
        'scoring':'Procedure accuracy and charged human-time estimates; no soak or engine run',
        'stand_ins':['Synthetic separate-part geometry and removal precedence',
                     'Synthetic initial bolt and surface conditions','Preprogrammed reference values'],
        'coverage':{'dowels':'Two source-backed retained head-dowel identities; condition, fit and removal not assessed',
                    'retained_body_source_inventory_sha256':config['geometry']['retained_body_source']['source_inventory_sha256'],
                    'real_geometry_precedence':'Finite-pose source obstructions do not grant complete removal permissions; fixture prerequisites remain labelled assumptions'},
        'labor_qualification':config['repair_scoring']['human_time_policy']['qualification'],
        'limits':{'child_timeout_seconds':PROCESS_TIMEOUT_SECONDS,'record_bytes':MAX_BYTES,
                  'stdout_stderr_byte_cap':None,'action_attempts':config['factors']['turn_budget']}}
    write(out/'report.json',canonical(report))
    members = sorted(path for path in out.rglob('*') if path.is_file())
    write(out/'SHA256SUMS',''.join(sha(path.read_bytes())+'  '+path.relative_to(out).as_posix()+'\n'
                                 for path in members).encode())
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    parser.add_argument('--worker',choices=['serve','replay'])
    for name in ('config','config-pin','source','source-pin','record'):
        parser.add_argument('--'+name)
    args=parser.parse_args()
    if args.worker:
        worker(args)
    else:
        run(args.out)


if __name__ == '__main__':
    main()
