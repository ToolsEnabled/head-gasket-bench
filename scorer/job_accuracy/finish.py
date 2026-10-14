"""Variant finish mistakes from resolved actions and typed final observations."""
from .independent import all_observed,component_bindings,finite


def observe(config, final, parts, fasteners, history):
    if not config.get('benchmark_task'):
        return {'mistakes':{},'detail':{},'unknown_types':[]}
    measured={(r['input'].get('target'),r['input'].get('kind')) for r in history if r['name']=='measure'}
    required={('head_face','flatness'),('block_deck','flatness')}
    required.update((p,'bolt_stretch') for p,f in fasteners.items() if f['group']=='head')
    missing=sorted(required-measured)
    belts=[p for p,d in parts.items() if d['role']=='timing_belt']
    original=belts[0] if len(belts)==1 else None
    current=component_bindings(parts,history).get(original,original)
    inspected={r['input'].get('target') for r in history if r['name']=='inspect'}
    within=[];surfaces={}
    for name in ('head_face','block_deck'):
        value=final.get('surfaces',{}).get(name,{}).get('warpage_m')
        limit=config['policy'].get('flatness_limits_m',{}).get(name,config['policy'].get('flatness_limit_m'))
        good=value<=limit if finite(value) and finite(limit) else None
        within.append(good);surfaces[name]={'warpage_m':value,'limit_m':limit,'within_limit':good}
    all_within=all_observed(within)
    damage=final.get('parts',{}).get(current,{}).get('damaged')
    tension=final.get('timing',{}).get('tensioned')
    mistakes={'missed_measurement':bool(missing),
              'missed_inspection':original not in inspected if original is not None else None,
              'wrong_service_decision':not all_within if all_within is not None else None,
              'wrong_part':damage if type(damage) is bool else None,
              'missed_belt_tension':not tension if type(tension) is bool else None}
    return {'mistakes':mistakes,'unknown_types':[k for k,v in mistakes.items() if v is None],
            'detail':{'missing_measurements':[list(v) for v in missing], 'surfaces':surfaces,
                      'original_belt':original,'active_belt':current,
                      'active_belt_damaged':damage,'belt_tensioned':tension}}
