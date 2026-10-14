"""Measured-use envelope and compact professional summary of one assessment."""
from copy import deepcopy
import math
from .independent import check, fingerprint


def run_report(assessment, *, wall_seconds=None, wall_source='Agent wall time was not supplied',
               tokens=None, token_source='Provider token receipt was not supplied',
               active_attempt=None, model_calls=None,
               model_call_source='Model call receipt was not supplied', api_cost=None):
    check(wall_seconds is None or type(wall_seconds) in (int,float)
          and math.isfinite(wall_seconds) and wall_seconds >= 0, 'report-wall')
    check(type(wall_source) is str and bool(wall_source.strip())
          and type(token_source) is str and bool(token_source.strip()), 'report-sources')
    check(tokens is None or type(tokens) is dict and set(tokens) == {'input','output'}
          and all(type(v) is int and v >= 0 for v in tokens.values()), 'report-tokens')
    check(active_attempt is None or type(active_attempt) is dict
          and active_attempt.get('status') == 'uncommitted_unknown'
          and type(active_attempt.get('reason')) is str and bool(active_attempt['reason'].strip()), 'report-active-attempt')
    check(model_calls is None or type(model_calls) is int and model_calls >= 0, 'report-model-calls')
    check(type(model_call_source) is str and bool(model_call_source.strip()), 'report-model-source')
    check(api_cost is None or type(api_cost) is dict and set(api_cost)=={'usd','source'}
          and type(api_cost['usd']) in (int,float) and math.isfinite(api_cost['usd']) and api_cost['usd'] >= 0
          and type(api_cost['source']) is str and bool(api_cost['source'].strip()), 'report-api-cost')
    return {'schema':'hgj/independent-repair-run-report/v1',
            'assessment_sha256':fingerprint(assessment), 'assessment':deepcopy(assessment),
            'agent_wall_time':{'seconds':wall_seconds,'status':'unknown' if wall_seconds is None else 'recorded',
                               'source':wall_source},
            'tokens':{'input':None if tokens is None else tokens['input'],
                      'output':None if tokens is None else tokens['output'],
                      'total':None if tokens is None else tokens['input']+tokens['output'],
                      'status':'unknown' if tokens is None else 'recorded', 'source':token_source},
            'committed_tool_calls':deepcopy(assessment['tool_calls']),
            'steps':{'model_calls':model_calls,'source':model_call_source},
            'api_equivalent_cost':{'usd':None if api_cost is None else api_cost['usd'],
                                   'source':'API-equivalent price was not supplied' if api_cost is None else api_cost['source']},
            'active_uncommitted_attempt':deepcopy(active_attempt),
            'measurement_scope':'Usage receipts are supplied separately; scoring wall time is never substituted for agent wall time'}


def number(value, suffix=''):
    return 'Unknown' if type(value) not in (int,float) or not math.isfinite(value) else f'{value:g}{suffix}'


def truth(value):
    return 'Unknown' if type(value) is not bool else 'Yes' if value else 'No'


def summary(report):
    a = report['assessment']; bolt = a['bolt_accuracy']; checklist = a['checklist_accuracy']
    done = a['status'] == 'finished'
    result=truth
    lines = ['# Repair assessment', '',
             ('Finish submitted' if done else 'Partial record; no successful finish')+'. '+
             'Terminal status: '+str(a['completion'].get('terminal_reason') or 'not supplied')+'.', '']
    primary=a.get('primary_score')
    if a.get('checkpoint_revision')=='amendment-1-20261009':
        lines += ['Checkpoint rules: Amendment 1, signed 9 October 2026. '+
                  'Each loosening pass may independently use either complete documented order; mixing orders within a pass fails. A serviceable original cover gasket may be inspected and refitted with sealant.', '']
    if a.get('checkpoint_revision')=='amendment-2-20261010':
        lines += ['Checkpoint rules: Amendment 2, signed 10 October 2026. '+
                  'One complete documented loosening order must be used consistently across all passes. A serviceable original cover gasket may be inspected and refitted with sealant.', '']
    if primary is not None:
        lines += [f"Success: {primary['S_full']}; score: {primary['S_partial']:.6g}; "
                  f"checkpoint points: {primary['points_earned']}/18.",
                  'Checkpoints not met: '+(', '.join(r['id'] for r in primary['checkpoints'] if not r['passed']) or 'none')+'.', '']
    else:
        lines += ['Primary checkpoint score was not computed for this historical assessment.', '']
    lines += ['Secondary accuracy covers the declared modeled items.', '',
             f"Modeled checklist: {number(checklist['final_accuracy_percent'], '%')} final; "
             f"{checklist['correct']}/{checklist['total']} items currently correct, {checklist['unknown']} unknown. "
             f"Head bolts: {number(bolt['final_accuracy_percent'], '%')} final; "
             f"{bolt['correct']}/{bolt['total']} raw criteria currently correct.", '',
             '| Position | Accuracy | Condition; stretch mm; damaged | Torque commands / expected Nm | Final state / expected Nm | Ranks / expected | Stage order |',
             '|---|---|---|---|---|---|---|']
    for row in bolt['bolts']:
        c = row['checks']
        stages=row['stages'];expected=row.get('expected_stages_N_m',[None,None])
        values=[number(None if stage is None else stage['value_N_m']) for stage in stages]
        ranks=[number(None if stage is None else stage['sequence_position']) for stage in stages]
        observed=row.get('final_observations',{})
        lines.append('| '+str(row['sequence_index'])+' | '+str(row['correct'])+'/6'+
                     ('; '+str(row['unknown'])+' unknown' if row['unknown'] else '')+' | '+result(c['bolt_condition'])+'; '+
                     number(observed.get('stretch_mm'))+'; '+result(observed.get('damaged'))+' | '+
                     ', '.join(values)+' / '+', '.join(number(v) for v in expected)+' | '+
                     number(observed.get('torque_N_m'))+' / '+number(expected[1])+' | '+
                     ', '.join(ranks)+' / '+str(row['sequence_index'])+' | '+result(c['stage_order'])+' |')
    h = a['human_time']; calls = a['tool_calls']
    lines += ['', f"Charged technician time: productive {number(h['productive_seconds'], ' s')}; "
              f"mistake penalties {number(h['penalty_seconds'], ' s')}; total {number(h['total_seconds'], ' s')}. "
              f"Correct reference: {number(h['reference_seconds'], ' s')}. {h['qualification']}", '',
              'Mistakes: '+(', '.join(f'{name.replace("_"," ")}: {count}' for name,count in a['mistakes']['by_type'].items()) or 'none recorded')+'.', '',
              f"Committed tool calls: {calls['attempted']} attempted, {calls['successful']} successful, {calls['refused']} refused. "
              f"Agent wall time: {number(report['agent_wall_time']['seconds'], ' s')}; "
              f"tokens: {number(report['tokens']['total'])}; model steps: {number(report['steps']['model_calls'])}; "
              f"API-equivalent cost: {number(report['api_equivalent_cost']['usd'], ' USD')}."]
    if report['agent_wall_time']['seconds'] is None: lines += [report['agent_wall_time']['source']+'.']
    if report['tokens']['total'] is None: lines += [report['tokens']['source']+'.']
    if h['unpriced_mistakes']:
        lines += ['', 'A required mistake penalty has no supplied rule; the total is unknown. '+
                  'Known charged subtotal: '+number(h['known_charged_subtotal_seconds'],' s')+'.']
    if h.get('unobserved_finish_mistake_types'):
        names=sorted({name.replace('_',' ') for row in h['unobserved_finish_mistake_types'] for name in row['types']})
        lines += ['', 'Finish observations cannot establish: '+', '.join(names)+'. '+
                  'The affected charge totals remain unknown; known charged subtotal: '+number(h['known_charged_subtotal_seconds'],' s')+'.']
    if report['active_uncommitted_attempt']:
        lines += ['', 'Uncommitted-attempt state is unknown: '+report['active_uncommitted_attempt']['reason']+'.']
    lines += ['', 'Coverage: '+a['coverage']['geometry_qualification']+'; dowels '+a['coverage']['dowels']+'. '+
              'Six raw checks per bolt retain both stage sequence checks separately. '+
              'The JSON report contains every checklist item, event and source commitment.', '',
              'Reference SHA256: `'+a['reference_sha256']+'`.']
    return '\n'.join(lines)+'\n'
