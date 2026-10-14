"""Independent reconstruction of the declared source removal procedure.

Only discrete part locations, attachments and configured route predicates are
replayed. No geometry, physical release or in-game evaluator is executed.
"""
from .independent import check,equal,finite,fingerprint,public_body_map,effective_role

MAX_POLICY_BODIES=2048
MAX_PREDICATE_DEPTH=32
MAX_PREDICATE_NODES=4096


def same_condition(actual, expected):
    return type(actual) is type(expected) and actual==expected


def installation_children(config, parts, carried, locations, carrier):
    # Installation scans the state body map; removal uses the chosen route.
    # Explicit initial conditions replace that map, including its iteration order.
    initial=config.get('initial_conditions')
    order=initial['values']['parts'] if initial else parts
    return [body for body in order if carried.get(body)==carrier and locations[body]=='tray']


def predicate(node, installed, released, conditions, *, depth=0, budget=None):
    budget=[MAX_PREDICATE_NODES] if budget is None else budget
    budget[0]-=1
    check(depth<=MAX_PREDICATE_DEPTH and budget[0]>=0,'removal-predicate-bound')
    check(type(node) is dict and len(node)==1,'removal-predicate-shape')
    op,value=next(iter(node.items()))
    if op in ('all','any'):
        check(type(value) is list and (op=='all' or len(value)>0),'removal-predicate-branch')
        results=[predicate(n,installed,released,conditions,depth=depth+1,budget=budget) for n in value]
        return all(results) if op=='all' else any(results)
    check(op in ('installed','removed','released','condition'),'removal-predicate-operator')
    if op=='condition':
        check(type(value) is dict and set(value)=={'id','equals'} and value['id'] in conditions
              and (type(value['equals']) in (bool,str) or finite(value['equals'])),'removal-condition-domain')
        actual=conditions[value['id']]
        return same_condition(actual,value['equals'])
    table=released if op=='released' else installed
    check(type(value) is str and value in table and type(table[value]) is bool,'removal-state-domain')
    return not table[value] if op=='removed' else table[value]


def replay(config, actions, final):
    spec=config.get('benchmark_removal')
    if spec is None:return {'available':False,'reason':'Source removal policy not supplied'}
    policy=spec['policy'];definitions=config['geometry']['parts'];parts={p['id']:p for p in definitions}
    rows={p['id']:p for p in policy['parts']}
    source={p['l1_body_id']:p['id'] for p in definitions if p.get('l1_selected_body') is True}
    check(policy['schema']=='engine-cad/benchmark-removal-policy/v1' and policy['physical_qualification'] is False
          and fingerprint(policy)==spec['policy_semantic_sha256'],'removal-policy-identity')
    check(0<len(rows)<=MAX_POLICY_BODIES and len(rows)==len(policy['parts'])
          and len(source)==sum(p.get('l1_selected_body') is True for p in definitions)
          and set(source)==set(rows) and equal(source,spec['source_to_body'])
          and all(equal(parts[body]['l1_binding'],rows[key]['binding']) for key,body in source.items()),'removal-source-census')
    releases={r['id']:r for r in policy['release_action_definitions']}
    check(len(releases)==len(policy['release_action_definitions'])==len(policy['release_actions'])==len(set(policy['release_actions']))
          and set(releases)==set(policy['release_actions'])
          and len(set(policy['condition_ids']))==len(policy['condition_ids']),'removal-attachment-census')
    released={k:False for k in releases};conditions={k:False for k in policy['condition_ids']}
    locations={p['id']:'assembly' if p['installed'] else 'unavailable' if p.get('available_in_bin') is False else 'supply' for p in definitions}
    original_sources={body:key for key,body in source.items()};replacements={};carried={}
    current=lambda key:replacements.get(key,source[key])
    installed=lambda:{key:locations[current(key)]=='assembly' for key in source}
    # Validate every branch once; false initial predicates are expected.
    for row in rows.values():
        carriers=row.get('carrier_ids',[])
        check(row['mode'] in ('individual','carried_with_assembly','retained_for_job')
              and type(row['routes']) is list and (row['mode']!='individual' or bool(row['routes']))
              and len({r['id'] for r in row['routes']})==len(row['routes'])
              and type(carriers) is list and len(carriers)==len(set(carriers))
              and all(c in rows and c!=row['id'] for c in carriers)
              and (row['mode']!='carried_with_assembly' or bool(carriers)),'removal-route-domain')
        for route in row['routes']:
            ids=route.get('carried_body_ids',[])
            check(type(ids) is list and len(ids)==len(set(ids)) and all(i in rows and i!=row['id'] for i in ids),'removal-moving-census')
            predicate(route['preconditions'],installed(),released,conditions)
    for release in releases.values():predicate(release['preconditions'],installed(),released,conditions)
    aliases=public_body_map(config);movements=[];attachments=[];observations=[];moved=set()
    fasteners={p['id']:p for p in config['geometry']['fasteners']};positions={k:k for k in fasteners}
    initial=config.get('initial_conditions',{}).get('values',{}).get('bolts',{})
    turns={pid:initial.get(pid,{}).get('turns') if config.get('initial_conditions') else f.get('initial_engagement_turns') for pid,f in fasteners.items()}
    setup=None;aligned_check=None
    # CP02 counts a refused removal as the environment does (paper Appendix C): the part named
    # is the installed current body of a source position and the policy blocks it (not an
    # individual removal, or no allowed route), or an allowed route of a scored fastener was
    # refused. A refused call keeps its input as given, so a stock label is not resolved.
    scored=set(initial) if config.get('initial_conditions') else set(fasteners);blocking=set()
    def body_source(pid):
        return original_sources.get(pid,next((key for key,value in replacements.items() if value==pid),None))
    def bound(pid):
        return current(original_sources[pid]) if pid in original_sources else pid
    for record in actions:
        name=record['name'];seq=record['seq'];ok=record['result']['ok'];raw=record['input']
        a={k:aliases.get(v,v) if k in ('part_id','replacement_id','target') and type(v) is str else v for k,v in raw.items()} if type(raw) is dict else {}
        pid=a.get('part_id');source_id=body_source(pid);reasons=[];moving=[];expected_receipt=None
        if name=='set_timing' and ok:
            setup=seq;aligned_check=None
        if name=='check_timing' and ok:
            aligned_check=seq if record['result'].get('observation',{}).get('marks_align') is True else None
        if name=='torque' and ok and pid in positions and a.get('mode')=='loosen':
            old=turns.get(pid);angle=a.get('angle_deg');turns[pid]=max(0,old+angle/360) if finite(old) and finite(angle) else None
        if name in ('prepare_condition','release_attachment','restore_attachment'):
            ident=a.get('condition_id') if name=='prepare_condition' else a.get('release_id')
            if name=='prepare_condition':
                if ident not in conditions:reasons.append('unknown-condition')
                if ident=='timing_marks_recorded' and not(setup is not None and aligned_check is not None and aligned_check>setup):reasons.append('missing-timing-setup-observation')
            else:
                if ident not in releases:reasons.append('unknown-attachment')
                elif name=='release_attachment':
                    if not predicate(releases[ident]['preconditions'],installed(),released,conditions):reasons.append('attachment-prerequisites')
                    for key in source:
                        body=current(key)
                        if ident in ('thread:'+key,'thread:'+key+':block_casting') and body in positions:
                            if not finite(turns.get(body)) or turns[body]>1e-9:reasons.append('thread-not-disengaged')
                elif not released[ident] or not all(installed().values()):reasons.append('attachment-restoration-order')
            if ok and not reasons:
                if name=='prepare_condition':conditions[ident]=True
                else:released[ident]=name=='release_attachment'
                expected_receipt={'seq':seq,'action':name,('condition_id' if name=='prepare_condition' else 'release_id'):ident}
                attachments.append(expected_receipt)
                actual=record['result'].get('receipt',{})
                if not all(equal(actual.get(k),v) for k,v in expected_receipt.items()):reasons.append('action-attachment-receipt')
        elif name=='remove' and source_id is not None:
            bench_seal=(parts[pid]['role']=='cover_gasket_old' and locations[pid]=='tray' and pid in carried and locations[carried[pid]]=='tray')
            if bench_seal:
                if ok:locations[pid]='waste';carried.pop(pid)
            else:
                row=rows[source_id]
                if current(source_id)!=pid or locations[pid]!='assembly':reasons.append('inactive-or-removed-body')
                if row['mode']!='individual':reasons.append('individual-removal-not-permitted')
                choices=[r for r in row['routes'] if a.get('route_id') is None or r['id']==a['route_id']]
                allowed=[r for r in choices if predicate(r['preconditions'],installed(),released,conditions)
                         and all(installed()[i] for i in r.get('carried_body_ids',[]))]
                route=allowed[0] if allowed else None
                if route is None:reasons.append('route-prerequisites')
                else:moving=[pid]+[current(i) for i in route.get('carried_body_ids',[])]
                blocked=[x for x in parts[pid]['requires_removed'] if locations.get(bound(x))=='assembly' and bound(x) not in moving]
                holders=[body for body,pos in positions.items() if locations.get(body)=='assembly' and body not in moving
                         and any(bound(h) in moving for h in (fasteners[pos].get('holds') or []))]
                if blocked or holders:reasons.append('installed-predecessor-or-holder')
                if pid in positions and (not finite(turns.get(pid)) or turns[pid]>1e-9):reasons.append('thread-not-disengaged')
                if (not ok and raw.get('part_id')==pid and 'inactive-or-removed-body' not in reasons
                        and (row['mode']!='individual' or route is None or pid in scored)):blocking.add(seq)
                if ok and not reasons:
                    for body in moving:locations[body]='waste' if body==pid and parts[body]['role']=='gasket_old' else 'tray'
                    for body in moving[1:]:carried[body]=pid
                    moved.update(body_source(body) for body in moving)
                    expected_receipt={'seq':seq,'action':'remove','body_id':pid,'source_body_id':source_id,
                                      'route_id':route['id'],'carried_body_ids':moving[1:]}
                    movements.append(expected_receipt)
                    if not equal(record['result'].get('carried_body_ids',[]),moving[1:]):reasons.append('action-moving-set')
        elif name=='replace' and ok:
            new=a['replacement_id']
            if source_id is not None:
                if current(source_id)!=pid or locations[pid] not in ('tray','waste') or locations[new]!='supply':reasons.append('exchange-location')
                oldrole=effective_role(parts[pid]);newrole=effective_role(parts[new])
                if not(oldrole==newrole or oldrole.startswith('gasket_') and newrole.startswith('gasket_') or oldrole.startswith('cover_gasket_') and newrole.startswith('cover_gasket_')):reasons.append('exchange-role')
                if parts[new].get('replacement_for') is not None and parts[new]['replacement_for']!=parts[pid].get('replacement_for',pid):reasons.append('exchange-position')
                if not reasons:
                    replacements[source_id]=new;locations[pid]='waste';locations[new]='tray'
                    for child,carrier in list(carried.items()):
                        if carrier==pid:carried[child]=new
            if pid in positions:
                positions[new]=positions[pid];turns[new]=initial.get(new,{}).get('turns') if config.get('initial_conditions') else 0
        elif name=='install' and ok:
            moving=[pid]+installation_children(config,parts,carried,locations,pid)
            if source_id is not None:
                if current(source_id)!=pid or locations[pid] not in ('tray','supply') or pid in carried:reasons.append('install-location-or-carrier')
                if any(locations.get(bound(mate))!='assembly' and bound(mate) not in moving for body in moving for mate in parts[body]['requires_installed']):reasons.append('install-support')
                if not reasons:
                    movements.append({'seq':seq,'action':'install','body_id':pid,'source_body_id':source_id,'carried_body_ids':moving[1:]})
                    if not equal(record['result'].get('carried_body_ids',[]),moving[1:]):reasons.append('action-moving-set')
            if not reasons:
                for body in moving:locations[body]='assembly';carried.pop(body,None)
                if pid in positions:turns[pid]=initial.get(pid,{}).get('install_engagement_turns') if config.get('initial_conditions') else 2
        if name in ('remove','install','replace','prepare_condition','release_attachment','restore_attachment'):
            observations.append({'sequence':seq,'name':name,'ok':ok,'source_body_id':source_id,'moving_body_ids':moving,
                                 'reasons':reasons,'valid':not reasons and ok})
    saved=final.get('benchmark_removal',{});mismatches=[];disassembly_mismatches=[]
    def compare(key,expected,actual):
        if not equal(expected,actual):mismatches.append(key)
    compare('policy_sha256',spec['policy_sha256'],saved.get('policy_sha256'))
    compare('released',released,saved.get('released'));compare('conditions',conditions,saved.get('conditions'))
    compare('replacements',replacements,saved.get('replacements'))
    for field,expected in [('movements',movements),('attachment_history',attachments)]:
        actual=saved.get(field)
        if type(actual) is not list or len(actual)!=len(expected):
            mismatches.append(field+'/count')
        else:
            for index,(want,got) in enumerate(zip(expected,actual)):
                if type(got) is not dict or any(not equal(got.get(k),v) for k,v in want.items()):
                    mismatches.append(field+'/'+str(index))

        dis_expected=[r for r in expected if r['action'] in ('remove','prepare_condition','release_attachment')]
        dis_actual=[r for r in actual if type(r) is dict and r.get('action') in ('remove','prepare_condition','release_attachment')] if type(actual) is list else []
        if len(dis_expected)!=len(dis_actual) or any(any(not equal(got.get(k),v) for k,v in want.items()) for want,got in zip(dis_expected,dis_actual)):
            disassembly_mismatches.append(field+'/disassembly')
    position_rows=[]
    for key in sorted(source):
        body=current(key);actual=final['parts'].get(body,{})
        compare('part/'+body+'/location',locations[body],actual.get('location'))
        compare('part/'+body+'/carried_with',carried.get(body),actual.get('carried_with'))
        position_rows.append({'source_position':key,'original_body':source[key],'current_body':body,
                              'mode':rows[key]['mode'],'moved':key in moved,'installed':actual.get('location')=='assembly',
                              'original_disposition_correct':body==source[key] or final['parts'][source[key]]['location']=='waste'})
    invalid=[r for r in observations if not r['valid']]
    # An executed invalid transition, or a refused removal counted above; other refusals change nothing.
    disassembly_invalid=[r for r in invalid if r['name'] in ('remove','prepare_condition','release_attachment')
                         and (r['ok'] or r['sequence'] in blocking)]
    return {'available':True,'source_positions':len(source),'scope':'Discrete source benchmark rules; no physical movement or release validation',
            'observations':observations,'positions':position_rows,'invalid_attempts':invalid,'state_mismatches':mismatches,
            'valid_disassembly':not disassembly_invalid and not disassembly_mismatches,
            'disassembly_invalid_attempts':disassembly_invalid,'disassembly_state_mismatches':disassembly_mismatches,
            'trace_consistent':not mismatches,
            'reassembly_complete':not mismatches and all(r['installed'] and r['original_disposition_correct'] for r in position_rows) and not any(released.values()),
            'expected_movements':movements,'expected_attachments':attachments,
            'final_released':released,'final_conditions':conditions,'final_replacements':replacements,
            'limits':{'bodies':MAX_POLICY_BODIES,'predicate_depth':MAX_PREDICATE_DEPTH,'predicate_nodes_per_expression':MAX_PREDICATE_NODES}}
