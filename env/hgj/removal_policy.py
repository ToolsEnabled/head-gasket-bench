"""Labelled benchmark removal predicates; never a physical qualification claim.

The caller owns state transitions and labor charges. This module evaluates a
chosen route against explicit body and release state, without modifying it.
"""
import json
import math


BASIS_KINDS={'measured_obstruction','authored_attachment','service_instruction','provisional_benchmark_rule'}
MODES={'individual','carried_with_assembly','retained_for_job'}


def require(value,message):
    if not value:raise ValueError('REMOVAL_POLICY_REFUSED: '+message)


def validate_predicate(node,body_ids,release_ids,condition_ids):
    require(type(node) is dict and len(node)==1,'a predicate must have exactly one operator')
    operator,value=next(iter(node.items()))
    if operator in ('all','any'):
        require(type(value) is list and (operator=='all' or len(value)>0),'invalid predicate branch')
        for child in value:validate_predicate(child,body_ids,release_ids,condition_ids)
    elif operator in ('removed','installed'):
        require(type(value) is str and value in body_ids,'unknown body in predicate')
    elif operator=='released':
        require(type(value) is str and value in release_ids,'unknown release action')
    elif operator=='condition':
        require(type(value) is dict and set(value)=={'id','equals'} and value['id'] in condition_ids,'unknown condition')
        require(type(value['equals']) in (str,bool,int,float) and
                (type(value['equals']) is not float or math.isfinite(value['equals'])),'invalid condition value')
    else:raise ValueError('REMOVAL_POLICY_REFUSED: unsupported predicate operator')


def validate_policy(policy,selected_bindings):
    require(policy['schema']=='engine-cad/benchmark-removal-policy/v1','unsupported policy schema')
    require(policy['physical_qualification'] is False,'benchmark rules cannot assert physical qualification')
    rows=policy['parts'];ids=[row['id'] for row in rows]
    require(len(ids)==len(set(ids)) and set(ids)==set(selected_bindings),'policy must account for every selected body exactly once')
    releases=policy['release_actions'];conditions=policy['condition_ids']
    require(len(releases)==len(set(releases)) and len(conditions)==len(set(conditions)),'repeated release or condition identity')
    if 'release_action_definitions' in policy:
        definitions = policy['release_action_definitions']
        require(len(definitions) == len(releases) and {r['id'] for r in definitions} == set(releases),
                'release definitions must match action identities exactly')
        for definition in definitions:
            validate_predicate(definition['preconditions'], set(ids), set(releases), set(conditions))
    for row in rows:
        require(json.dumps(row['binding'],sort_keys=True,allow_nan=False)==json.dumps(selected_bindings[row['id']],sort_keys=True,allow_nan=False),'selected body identity or pose changed')
        require(row['mode'] in MODES,'unknown job disposition')
        require(bool(row['basis']) and all(b['kind'] in BASIS_KINDS and bool(b['explanation']) and bool(b['sources']) for b in row['basis']),
                'each decision requires a labelled basis and source')
        carriers=row.get('carrier_ids',[])
        require(len(carriers)==len(set(carriers)) and all(c in selected_bindings and c!=row['id'] for c in carriers),'invalid carrier identity')
        if row['mode']=='carried_with_assembly':require(bool(carriers),'carried part needs an explicit carrier')
        routes=row['routes'];names=[r['id'] for r in routes]
        require(len(names)==len(set(names)) and (row['mode']!='individual' or bool(routes)),'individual removal needs named routes')
        for route in routes:
            validate_predicate(route['preconditions'],set(ids),set(releases),set(conditions))
            require(bool(route['direction_basis']) and bool(route['service_context']),'route needs direction and service context')
            direction=route['direction']
            require(type(direction) is list and len(direction)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in direction)
                    and sum(v*v for v in direction)>0,'finite nonzero service direction required')
            carried=route.get('carried_body_ids',[])
            require(len(carried)==len(set(carried)) and all(c in selected_bindings and c!=row['id'] for c in carried),'invalid route moving set')
    return {row['id']:row for row in rows}


def evaluate_predicate(node,state):
    operator,value=next(iter(node.items()))
    if operator in ('all','any'):
        results=[evaluate_predicate(child,state) for child in value]
        missing=[item for r in results for item in r['missing']]
        if operator=='all':
            satisfied=all(r['satisfied'] for r in results)
            if any(not r['satisfied'] and not r['missing'] for r in results):missing=[]
        else:
            satisfied=any(r['satisfied'] for r in results)
            if satisfied:missing=[]
        return {'satisfied':satisfied,'missing':missing,'operator':operator,'children':results}
    table='installed' if operator in ('removed','installed') else ('released' if operator=='released' else 'conditions')
    ident=value if operator!='condition' else value['id']
    if table not in state or ident not in state[table]:
        return {'satisfied':False,'missing':[{'table':table,'id':ident}],'operator':operator,'value':value}
    actual=state[table][ident]
    if operator in ('removed','installed','released'):
        require(type(actual) is bool,'body and release states must be explicit booleans')
        satisfied=(not actual) if operator=='removed' else actual
    else:satisfied=type(actual) is type(value['equals']) and actual==value['equals']
    return {'satisfied':satisfied,'missing':[],'operator':operator,'value':value,'actual':actual}


def evaluate_removal(row,state,route_id=None):
    ident=row['id']
    if ident not in state.get('installed',{}):return {'decision':'INPUT_INCOMPLETE','part_id':ident,'reason':'Body state is missing.','physical_qualification':False}
    require(type(state['installed'][ident]) is bool,'body state must be an explicit boolean')
    if not state['installed'][ident]:return {'decision':'ALREADY_REMOVED','part_id':ident,'physical_qualification':False}
    if row['mode']!='individual':
        return {'decision':'RETAINED_FOR_JOB' if row['mode']=='retained_for_job' else 'REMOVE_WITH_ASSEMBLY',
                'part_id':ident,'carrier_ids':row.get('carrier_ids',[]),'basis':row['basis'],'physical_qualification':False}
    routes=[r for r in row['routes'] if route_id is None or r['id']==route_id]
    require(bool(routes),'unknown requested route')
    results=[{'route_id':r['id'],'predicate':evaluate_predicate({'all':[r['preconditions']] + [{'installed':i} for i in r.get('carried_body_ids',[])]},state)} for r in routes]
    allowed=[r['route_id'] for r in results if r['predicate']['satisfied']]
    decision='ALLOWED_BY_BENCHMARK_RULE' if allowed else ('INPUT_INCOMPLETE' if any(r['predicate']['missing'] for r in results) else 'BLOCKED_BY_BENCHMARK_RULE')
    return {'decision':decision,'part_id':ident,'allowed_route_ids':allowed,'route_results':results,'basis':row['basis'],
            'physical_qualification':False,'state_changed':False}


def evaluate_release(definition, state):
    """Check an attachment action before the caller records its transition."""
    result = evaluate_predicate(definition['preconditions'], state)
    return {'decision': 'ALLOWED_BY_BENCHMARK_RULE' if result['satisfied'] else
            ('INPUT_INCOMPLETE' if result['missing'] else 'BLOCKED_BY_BENCHMARK_RULE'),
            'release_id': definition['id'], 'predicate': result,
            'physical_qualification': False, 'state_changed': False}
