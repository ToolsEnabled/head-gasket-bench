"""Authored value tests of all twelve checkpoints; never executes a repair."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
from job_accuracy import checkpoints as cp
from job_accuracy.independent import AssessmentInputError, encoded, fingerprint


def commit(record):
    """Recommit deliberately authored records, preserving their value-test label."""
    config=record['config'];reference=config['repair_scoring']['reference']
    reference['geometry_sha256']=fingerprint(config['geometry'])
    config['repair_scoring']['reference_sha256']=fingerprint(reference)
    record['config_sha256']=fingerprint(config)
    aliases={('stock_'+fingerprint({'body_id':p['id'],'variant':config['variant_id']})[:12]
              if p['role'] in ('gasket_new','gasket_wrong') else p['id']):p['id'] for p in config['geometry']['parts']}
    history=[]
    for row in record['actions']:
        if row['result']['ok'] is True:
            args={k:aliases.get(v,v) if k in ('part_id','replacement_id','target') and type(v) is str else v for k,v in row['input'].items()}
            history.append({'seq':row['seq'],'name':row['name'],'input':args})
    record['final_state']['action_history']=history
    record['final_state']['identity']['action_history_sha256']=fingerprint(history)
    record['final_state_sha256']=fingerprint(record['final_state'])
    record['actions'][-1]['post_state_sha256']=record['final_state_sha256']
    previous=record['config_sha256']
    for row in record['actions']:
        row['previous_action_sha256']=previous;previous=fingerprint(row)
    return record


def authored_complete(original):
    r=deepcopy(original);c=r['config'];f=r['final_state'];ref=c['repair_scoring']['reference']
    r['authored_fixture']='Value-test augmentation only; observations were not produced by an environment or agent'
    row=r['actions'][0];row.update(name='check_timing',input={'crank_revolutions':2},result={'ok':True,'observation':{'tdc_cylinder':1,'marks_align':True}})
    next(p for p in c['geometry']['parts'] if p['role']=='gasket_new')['catalog']['bore_mm']=75
    c['policy'].update(flatness_limits_m={'head_face':0.00005,'block_deck':0.0001},flatness_limit_source_ids=['S1'])
    part=deepcopy(next(p for p in c['geometry']['parts'] if p['role']=='block'))
    part.update(id='authored_alignment_dowel',role='head_dowel',installed=True)
    c['geometry']['parts'].append(part)
    f['parts'][part['id']]=deepcopy(f['parts']['block']);ref['final']['parts'][part['id']]=deepcopy(f['parts']['block'])
    f['gasket']['dowels_aligned']=True;f['timing']['belt_tensioned']=True
    return commit(r)


def evaluate(record):
    s=record['config']['repair_scoring'];return cp.score(record,s['reference'],s['human_time_policy'],terminal_reason='authored_value_test')


def mutants(base):
    rows=[]
    def add(ident,fn):
        r=deepcopy(base);fn(r);rows.append((ident,commit(r)))
    def lookups(r):
        for row in r['actions']:
            if row['name']=='search_service_info':row['result']['entries']=[e for e in row['result']['entries'] if e['id']!='E04']
    add('CP01',lookups)
    add('CP02',lambda r:r['actions'][1].update(name='remove',input={'part_id':'head'},result={'ok':False,'error':'Authored blocked removal'}))
    add('CP03',lambda r:r['actions'][0]['result']['observation'].update(tdc_cylinder=2))
    def loosen(r):
        next(x for x in r['actions'] if x['name']=='torque' and x['input'].get('part_id')=='hb10' and x['input'].get('mode')=='loosen')['input']['angle_deg']=-60
    add('CP04',loosen)
    add('CP05',lambda r:r['final_state']['surfaces']['head_face'].update(damaged=True))
    add('CP06',lambda r:r['config']['policy']['flatness_limits_m'].update(head_face=0.00001))
    def measurement(r):
        next(x for x in r['actions'] if x['name']=='measure' and x['input'].get('target')=='hb01')['result']['observation']['value']=True
    add('CP07',measurement)
    add('CP08',lambda r:r['final_state']['gasket'].update(dowels_aligned=False))
    def torque(r,old,new):
        next(x for x in r['actions'] if x['name']=='torque' and x['input'].get('part_id')=='hb01' and x['input'].get('value_N_m')==old)['input']['value_N_m']=new
        if old==73:r['final_state']['bolts']['hb01']['torque_N_m']=new
    add('CP09',lambda r:torque(r,30,25))
    add('CP10',lambda r:torque(r,73,70))
    add('CP11',lambda r:r['final_state']['timing'].update(belt_tensioned=False))
    add('CP12',lambda r:r['final_state']['parts']['cover'].update(location='tray'))
    return rows


def run(inputs,out):
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic();original=json.loads(inputs.read_bytes())
    authored=authored_complete(original);baseline=evaluate(authored);raw=evaluate(original)
    assert baseline['primary_score']['S_full']==baseline['primary_score']['S_partial']==1
    assert baseline['primary_score']['points_earned']==18
    (out/'AUTHORED-COMPLETE-VALUE-FIXTURE.json').write_bytes(encoded(authored))
    (out/'AUTHORED-COMPLETE-ASSESSMENT.json').write_bytes(encoded(baseline))
    (out/'ORIGINAL-RETAINED-ASSESSMENT.json').write_bytes(encoded(raw))
    predicate=cp.checkpoint_pass;checks=[]
    for ident,record in mutants(authored):
        def observation():
            primary=evaluate(record)['primary_score'];row=next(x for x in primary['checkpoints'] if x['id']==ident)
            return {'passed':row['passed'],'points':primary['points_earned'],'S_full':primary['S_full'],'S_partial':primary['S_partial'],'not_met':row['not_met']}
        before=observation()
        with patch.object(cp,'checkpoint_pass',lambda code,values:True if code==ident else predicate(code,values)):
            omitted=observation()
        restored=observation()
        checks.append({'checkpoint':ident,'before':before,'omitted':omitted,'restored':restored,
                       'red':omitted['passed'] is True,'green':before==restored and before['passed'] is False})
    guard=cp.check;gates=[]
    for code in ('checkpoint-census','checkpoint-values'):
        rows=deepcopy(baseline['primary_score']['checkpoints'])
        if code=='checkpoint-census':rows.pop()
        else:rows[0]['passed']=1
        def call():
            try:cp.weighted_score(rows)
            except AssessmentInputError as e:return {'refused':e.code}
            return {'accepted':True}
        before=call()
        with patch.object(cp,'check',lambda condition,name:None if name==code else guard(condition,name)):omitted=call()
        restored=call();gates.append({'gate':code,'before':before,'omitted':omitted,'restored':restored,
                                    'red':omitted=={'accepted':True},'green':before==restored=={'refused':code}})
    formula=[]
    for failed in ([],[0],[1],list(range(12))):
        rows=deepcopy(baseline['primary_score']['checkpoints'])
        for i in failed:rows[i]['passed']=False
        result=cp.weighted_score(rows);expected_earned=18-sum(cp.DEFINITIONS[i][1] for i in failed)
        expected_full=int(not failed);expected_partial=expected_earned/36+0.5*expected_full
        formula.append({'failed':failed,'points':result['points_earned'],'S_full':result['S_full'],'S_partial':result['S_partial'],
                        'passed':result['points_earned']==expected_earned and result['S_full']==expected_full and result['S_partial']==expected_partial})
    sources={}
    from job_accuracy import independent
    for p in (Path(cp.__file__),Path(independent.__file__),Path(__file__)):
        b=p.read_bytes();(out/p.name).write_bytes(b);sources[p.name]=hashlib.sha256(b).hexdigest()
    allgreen=all(x['red'] and x['green'] for x in checks+gates) and all(x['passed'] for x in formula)
    result={'status':'GREEN' if allgreen else 'RED','checkpoint_mutations':checks,'gate_mutations':gates,'formula_values':formula,
            'source_sha256':sources,'input_sha256':hashlib.sha256(inputs.read_bytes()).hexdigest(),'environment_executions':0,
            'wall_seconds':time.monotonic()-start,'authored_baseline':{'S_full':1,'S_partial':1,'points':18},
            'original_retained_baseline':{k:raw['primary_score'][k] for k in ('S_full','S_partial','points_earned')},
            'scope':'Authored values validate proposed observation fields. The old recorded repair is separately scored and fails missing observations; this is not the required new scripted baseline.'}
    (out/'result.json').write_bytes(encoded(result));print(json.dumps({'status':result['status'],'checkpoint_mutations':len(checks),'gate_mutations':len(gates),'formula_cases':len(formula),'original':result['original_retained_baseline']}))
    if not allgreen:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.input,a.out)
