"""Signed twelve-checkpoint reducer; independent of the external L2 reducer."""
import copy
import math
from .codec import canonical
from .removal_policy import evaluate_removal, evaluate_release

DEFINITIONS = (
    ('CP01',1,'Service lookup before head tightening'),
    ('CP02',2,'Valid disassembly'),
    ('CP03',1,'TDC and aligned marks before belt removal'),
    ('CP04',1,'Staged head loosening'),
    ('CP05',1,'Mating surfaces cleaned before gasket placement'),
    ('CP06',1,'Flatness measured before the correct service decision'),
    ('CP07',1,'Bolts measured before the correct keep or replace decision'),
    ('CP08',2,'Correct new gasket and aligned dowels'),
    ('CP09',2,'Valid first torque stage'),
    ('CP10',2,'Valid final torque stage'),
    ('CP11',2,'Timing restored and checked'),
    ('CP12',2,'Parts and attachments restored'),
)


ORIGINAL_REVISION = 'signoff-20261009'
AMENDMENT_REVISION = 'amendment-1-20261009'


def checkpoint_revision(config):
    revision = config.get('checkpoint_revision', ORIGINAL_REVISION)
    if revision not in (ORIGINAL_REVISION, AMENDMENT_REVISION):
        raise ValueError('Unknown checkpoint revision')
    return revision


AMENDMENT_LOOSENING_ORDERS = (
    (10, 9, 8, 7, 6, 3, 4, 5, 2, 1),
    (10, 9, 8, 7, 6, 5, 4, 3, 2, 1),
)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _carries(row, body):
    members = row.get('result', {}).get('carried_body_ids', [])
    return (type(members) is list and all(type(member) is str for member in members)
            and len(members) == len(set(members)) and body in members)


def loosening_assessment(config, initial, rows):
    """One whole accepted order, with reference-counted benchmark passes.

    Only successful head-position loosening before the first successful head
    removal counts. Prefix candidate narrowing is stable as the journal grows:
    an invalid event is recorded without switching a previously selected order.
    """
    parts = {p['id']: p for p in config['geometry']['parts']}
    fasteners = [f for f in config['geometry']['fasteners']
                 if f['group'] == 'head' and f.get('service_required', True)]
    indexes = {f['sequence_index']: f['id'] for f in fasteners}
    census = (len(fasteners) == 10 and len(indexes) == 10
              and len({f['id'] for f in fasteners}) == 10
              and all(type(f['sequence_index']) is int for f in fasteners)
              and set(indexes) == set(range(1, 11)))
    members = {f['id'] for f in fasteners}
    heads = {pid for pid, p in parts.items() if p['role'] in ('head', 'head_supply')}
    successful = [r for r in rows if r.get('ok') is True]
    first_head = min((r['seq'] for r in successful if r['name'] == 'remove'
                      and r['input'].get('part_id') in heads), default=None)
    all_loosen = [r for r in successful if r['name'] == 'torque'
                  and r['input'].get('part_id') in members
                  and r['input'].get('mode') == 'loosen']
    observed = [r for r in all_loosen if first_head is None or r['seq'] < first_head]
    reference = [r['input'] for r in config['repair_scoring']['reference']['actions']
                 if r['name'] == 'torque' and r['input'].get('part_id') in members
                 and r['input'].get('mode') == 'loosen']
    reference_valid = (census and bool(reference) and len(reference) % 10 == 0
                       and all(_number(a.get('angle_deg')) and a['angle_deg'] == -120
                               for a in reference))
    passes = len(reference) // 10
    candidates = [[indexes[i] for i in order] * passes
                  for order in AMENDMENT_LOOSENING_ORDERS] if reference_valid else []
    remaining = list(range(len(candidates)))
    order_violations, increment_violations = [], []
    turns = {pid: initial['bolts'].get(pid, {}).get('turns') for pid in members}
    for index, row in enumerate(observed):
        args = row['input']; pid = args['part_id']; angle = args.get('angle_deg')
        matching = [n for n in remaining if index < len(candidates[n])
                    and candidates[n][index] == pid]
        if matching:
            remaining = matching
        else:
            order_violations.append(row['seq'])
        if not _number(angle) or angle != -120:
            increment_violations.append(row['seq'])
        if _number(turns.get(pid)) and _number(angle):
            turns[pid] += angle / 360
        else:
            turns[pid] = None
    order_valid = (reference_valid and len(observed) == len(reference)
                   and not order_violations and bool(remaining))
    increments_valid = reference_valid and not increment_violations
    disengaged = bool(turns) and all(_number(t) and t <= 1e-9 for t in turns.values())
    passed = (first_head is not None and bool(observed) and order_valid
              and increments_valid and disengaged)
    return {
        'passed': passed, 'order_valid': order_valid,
        'increments_valid': increments_valid, 'disengaged': disengaged,
        'head_removal_observed': first_head is not None,
        'reference_valid': reference_valid, 'expected_passes': passes,
        'observed_sequences': [r['seq'] for r in observed],
        'violation_sequences': sorted(set(order_violations + increment_violations)),
        'order_violation_sequences': order_violations,
        'increment_violation_sequences': increment_violations,
        'accepted_order': list(AMENDMENT_LOOSENING_ORDERS[remaining[0]])
                          if order_valid else None,
        'scope': 'Signed two-order rule; pass count and initial engagement are benchmark inputs',
    }


def cover_gasket_assessment(config, rows, final):
    """Check distinct new-seal and current-cycle inspected-original routes."""
    parts = {p['id']: p for p in config['geometry']['parts']}
    originals = [pid for pid, p in parts.items() if p['role'] == 'cover_gasket_old']
    new_ids = {pid for pid, p in parts.items() if p['role'] == 'cover_gasket_new'}
    covers = {pid for pid, p in parts.items() if p['role'] == 'valve_cover'}
    original = originals[0] if len(originals) == 1 else None
    candidates = [pid for pid in ([original] if original else []) + sorted(new_ids)
                  if final['parts'].get(pid, {}).get('location') == 'assembly']
    active = candidates[0] if len(candidates) == 1 else None
    source_original = config.get('benchmark_removal', {}).get('source_to_body', {}).get('valve_cover_gasket_old')
    mapped = final.get('benchmark_removal', {}).get('replacements', {}).get('valve_cover_gasket_old', source_original)
    binding_valid = original is not None and source_original == original and active == mapped
    route = 'original_reuse' if active is not None and active == original else (
        'new' if active in new_ids else 'unresolved')
    successful = [r for r in rows if r.get('ok') is True]
    installs = [r for r in successful if r['name'] == 'install' and (
        r['input'].get('part_id') == active or
        r['input'].get('part_id') in covers and
        _carries(r, active))]
    fitted = max(installs, key=lambda r: r['seq'], default=None)
    removals = [r for r in successful if r['name'] == 'remove' and (
        r['input'].get('part_id') == original
        or r['input'].get('part_id') in covers
           and _carries(r, original))]
    boundary = max((r['seq'] for r in removals), default=None)
    prior = [r for r in successful if boundary is not None and fitted is not None
             and boundary < r['seq'] < fitted['seq']]
    inspections = [r for r in prior if r['name'] == 'inspect'
                   and r['input'].get('target') == original]
    inspection = max(inspections, key=lambda r: r['seq'], default=None)
    inspection_valid = (inspection is not None and
        inspection.get('result', {}).get('observation', {}).get('damaged') is False)
    treatments = [r for r in successful if r['name'] == 'clean'
                  and r['input'].get('target') == 'cover_face']
    treatment = max(treatments, key=lambda r: r['seq'], default=None)
    face = final.get('surfaces', {}).get('cover_face', {})
    treatment_valid = (treatment is not None and boundary is not None and fitted is not None
        and boundary < treatment['seq'] < fitted['seq']
        and treatment['input'].get('protect_openings') is True
        and treatment['input'].get('oil') is True
        and treatment['input'].get('sealant') == 'cam_holder_corners'
        and face.get('tube_seals_oiled') is True
        and face.get('cam_holder_corner_sealant') is True
        and _number(face.get('residue_fraction')) and face['residue_fraction'] == 0
        and face.get('dry') is True and face.get('damaged') is False
        and type(face.get('debris_count')) is int and face['debris_count'] == 0)
    refit_valid = (original is not None and active is not None and fitted is not None
        and boundary is not None and fitted['seq'] > boundary
        and final['parts'][active].get('damaged') is False)
    exchanges = [r for r in prior if r['name'] == 'replace'
                 and r['input'].get('part_id') == original
                 and r['input'].get('replacement_id') == active]
    new_valid = (route == 'new' and bool(exchanges)
                 and final['parts'].get(original, {}).get('location') == 'waste')
    reuse_valid = route == 'original_reuse' and inspection_valid
    passed = binding_valid and refit_valid and treatment_valid and (new_valid or reuse_valid)
    evidence = removals + installs + inspections + exchanges
    if treatment is not None:
        evidence.append(treatment)
    return {
        'passed': passed, 'route': route, 'original_id': original, 'active_id': active,
        'current_cycle_start': boundary, 'source_binding_valid': binding_valid,
        'inspection_valid': inspection_valid,
        'treatment_valid': treatment_valid, 'refit_valid': refit_valid,
        'new_replacement_valid': new_valid, 'original_reuse_valid': reuse_valid,
        'evidence_sequences': sorted({r['seq'] for r in evidence}),
        'scope': 'Amendment 1 cover seal alternative only; new head gasket remains mandatory',
    }


def replacement_allowed(requirement, evidence):
    """L1 source3 build_l1_job_checklists.replacement_allowed predicate."""
    return any(all(evidence.get(key) is True for key in option['required_true'])
               for option in requirement.get('replacement_options', []))


def cover_refit_assessments(config, initial, rows):
    """Keep each installation's own seal witnesses, including corrected errors.

    This small projection follows recorded discrete bench transitions only.
    Final acceptance still uses the actual exported final state.
    """
    definitions = {p['id']: p for p in config['geometry']['parts']}
    ids = {p for p, d in definitions.items()
           if d['role'] in ('cover_gasket_old', 'cover_gasket_new', 'valve_cover')}
    state = {'parts': {p: copy.deepcopy(initial['parts'][p]) for p in ids},
             'surfaces': {'cover_face': copy.deepcopy(initial['surfaces']['cover_face'])},
             'benchmark_removal': {'replacements': copy.deepcopy(
                 initial.get('benchmark_removal', {}).get('replacements', {}))}}
    prefix, output = [], {}
    for row in rows:
        prefix.append(row)
        if row.get('ok') is not True:
            continue
        a = row['input']; name = row['name']; pid = a.get('part_id')
        if name in ('remove', 'install'):
            carried = row.get('result', {}).get('carried_body_ids', [])
            moving = [pid] + (carried if type(carried) is list else [])
            for body in moving:
                if type(body) is str and body in ids:
                    state['parts'][body]['location'] = 'assembly' if name == 'install' else 'tray'
            if name == 'remove' and pid in ids and definitions[pid]['role'] == 'cover_gasket_old':
                state['parts'][pid]['location'] = 'waste'
        elif name == 'replace' and pid in ids:
            new = a.get('replacement_id')
            if new in ids:
                state['parts'][pid]['location'] = 'waste'
                state['parts'][new]['location'] = 'tray'
                state['benchmark_removal']['replacements']['valve_cover_gasket_old'] = new
        elif name == 'clean' and a.get('target') == 'cover_face':
            face = state['surfaces']['cover_face']
            face.update(residue_fraction=0, dry=True,
                        tube_seals_oiled=a.get('oil', False),
                        cam_holder_corner_sealant=a.get('sealant') == 'cam_holder_corners')
            if a.get('protect_openings') is not True:
                face['debris_count'] += 1
            if a.get('method') == 'abrasive_disc':
                face['damaged'] = True
        if name == 'install' and (pid in ids and definitions[pid]['role'].startswith('cover_gasket_')
                or any(definitions[p]['role'] in ('cover_gasket_old', 'cover_gasket_new')
                       and _carries(row, p) for p in ids)):
            output[row['seq']] = cover_gasket_assessment(config, prefix, state)
    return output


def equal(a,b):
    return canonical(a)==canonical(b)


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def role(part):
    return {'head_supply':'head','timing_belt_supply':'timing_belt'}.get(part['role'],part['role'])


def disassembly(config, initial, rows):
    spec=config.get('benchmark_removal')
    if spec is None:
        return {'source_policy_present':False}, []
    policy=spec['policy'];definitions={p['id']:p for p in policy['parts']}
    releases={r['id']:r for r in policy['release_action_definitions']}
    bodies=dict(spec['source_to_body'])
    start=initial['benchmark_removal']
    bodies.update(start.get('replacements',{}))
    state={'installed':{k:initial['parts'][v]['location']=='assembly' for k,v in bodies.items()},
           'released':copy.deepcopy(start['released']),'conditions':copy.deepcopy(start['conditions'])}
    by_body={body:source for source,body in bodies.items()}
    bad=[];removed=[]
    for row in rows:
        a=row['input'] if isinstance(row['input'],dict) else {}
        name=row['name'];ok=row['ok'];pid=a.get('part_id')
        source=by_body.get(pid) if isinstance(pid,str) else None
        if name=='prepare_condition' and ok:
            state['conditions'][a['condition_id']]=True
        elif name=='release_attachment':
            ident=a.get('release_id')
            decision=evaluate_release(releases[ident],state) if ident in releases else None
            if ok:
                if decision is None or decision['decision']!='ALLOWED_BY_BENCHMARK_RULE':
                    bad.append(row['seq'])
                state['released'][ident]=True
        elif name=='restore_attachment' and ok:
            state['released'][a['release_id']]=False
        elif name=='replace' and ok and source is not None:
            by_body.pop(bodies[source],None)
            bodies[source]=a['replacement_id'];by_body[a['replacement_id']]=source
            state['installed'][source]=False
        elif name=='remove' and source is not None:
            decision=evaluate_removal(definitions[source],state,a.get('route_id'))
            if ok:
                # An explicitly exposed tray-only cover-seal operation is a
                # separate bench detach, after source removal with the cover.
                bench=(source=='valve_cover_gasket_old' and state['installed'][source] is False)
                if not bench and decision['decision']!='ALLOWED_BY_BENCHMARK_RULE':
                    bad.append(row['seq'])
                if not bench and decision['decision']=='ALLOWED_BY_BENCHMARK_RULE':
                    route=next(r for r in definitions[source]['routes'] if r['id']==decision['allowed_route_ids'][0])
                    expected=[bodies[k] for k in route.get('carried_body_ids',[])]
                    if set(row['result'].get('carried_body_ids',[]))!=set(expected):
                        bad.append(row['seq'])
                moving=[pid,*row['result'].get('carried_body_ids',[])]
                for body in moving:
                    key=by_body.get(body)
                    if key is not None:state['installed'][key]=False
                removed.append(row['seq'])
            elif decision['decision'] in ('BLOCKED_BY_BENCHMARK_RULE','REMOVE_WITH_ASSEMBLY','RETAINED_FOR_JOB'):
                bad.append(row['seq'])
            elif decision['decision']=='ALLOWED_BY_BENCHMARK_RULE':
                # The source route may be open while a scored thread is still
                # mechanically engaged; the environment's named refusal counts.
                if pid in initial.get('bolts',{}):bad.append(row['seq'])
        elif name=='install' and ok and source is not None:
            moving=[pid,*row['result'].get('carried_body_ids',[])]
            for body in moving:
                key=by_body.get(body)
                if key is not None:state['installed'][key]=True
    return {'source_policy_present':True,'disassembly_observed':bool(removed),
            'all_removal_and_release_transitions_valid':not bad},sorted(set(removed+bad))


def evaluate(config, initial, rows, final, secondary, attachments):
    parts={p['id']:p for p in config['geometry']['parts']}
    fasteners={f['id']:f for f in config['geometry']['fasteners']}
    reference=config['repair_scoring']['reference']
    successful=[r for r in rows if r['ok']]
    def performed(name,predicate=lambda a:True):
        return [r for r in successful if r['name']==name and predicate(r['input'])]
    def role_ids(name):
        return {p for p,d in parts.items() if role(d)==name}
    heads,belts=role_ids('head'),role_ids('timing_belt')
    bolts=secondary['bolt_accuracy']['bolts']
    items={r['item']:r['correct'] for r in secondary['checklist_accuracy']['items']}
    output=[]
    def add(number,checks,sequences=()):
        ident,weight,title=DEFINITIONS[number-1]
        output.append({'id':ident,'weight':weight,'title':title,
                       'passed':bool(checks) and all(v is True for v in checks.values()),
                       'requirements':checks,'not_met':[k for k,v in checks.items() if v is not True],
                       'evidence_sequences':sorted(set(sequences))})
    tightening=performed('torque',lambda a:a.get('part_id') in role_ids('head_bolt') and a.get('mode')=='tighten')
    first_tighten=min((r['seq'] for r in tightening),default=None)
    searches=[r for r in performed('search_service_info') if first_tighten is not None and r['seq']<first_tighten]
    seen={e['id'] for r in searches for e in r['result'].get('entries',[])}
    categories=config['repair_scoring']['lookup_categories']
    add(1,{'head_tightening_observed':first_tighten is not None,
           'torque_stages_retrieved':bool(categories.get('torque')) and set(categories['torque'])<=seen,
           'sequence_retrieved':bool(categories.get('sequence')) and set(categories['sequence'])<=seen},[r['seq'] for r in searches])
    checks,seqs=disassembly(config,initial,rows);add(2,checks,seqs)
    belt_removes=performed('remove',lambda a:a.get('part_id') in belts)
    first_belt=min((r['seq'] for r in belt_removes),default=None)
    prior_changes=[r['seq'] for r in successful if first_belt is not None and r['seq']<first_belt
                   and (r['name']=='set_timing' or r['name'] in ('install','replace','tension_belt')
                        and r['input'].get('part_id') in belts)]
    setup_boundary=max(prior_changes,default=0)
    pre=[r for r in performed('check_timing') if first_belt is not None and setup_boundary<r['seq']<first_belt]
    witness=max(pre,key=lambda r:r['seq'],default=None)
    observation={} if witness is None else witness['result'].get('observation',{})
    add(3,{'belt_removal_observed':first_belt is not None,
           'prior_tdc_observed':type(observation.get('tdc_cylinder')) is int and observation['tdc_cylinder']==1,
           'prior_marks_aligned':observation.get('marks_align') is True},[r['seq'] for r in pre+belt_removes])
    removed_heads=performed('remove',lambda a:a.get('part_id') in heads)
    first_head=min((r['seq'] for r in removed_heads),default=None)
    original_head={p for p,f in fasteners.items() if f['group']=='head' and f.get('service_required',True)}
    loosen=[r for r in performed('torque',lambda a:a.get('part_id') in original_head and a.get('mode')=='loosen')
            if first_head is not None and r['seq']<first_head]
    expected=[r['input'] for r in reference['actions'] if r['name']=='torque'
              and r['input'].get('part_id') in original_head and r['input'].get('mode')=='loosen']
    def loosening_value(a,b):
        return a.get('part_id')==b.get('part_id') and a.get('mode')==b.get('mode')=='loosen' and finite(a.get('angle_deg')) and a['angle_deg']==b['angle_deg']
    amendment = checkpoint_revision(config) == AMENDMENT_REVISION
    if amendment:
        loosened = loosening_assessment(config, initial, rows)
        add(4, {key:loosened[key] for key in ('head_removal_observed', 'reference_valid',
               'order_valid', 'increments_valid', 'disengaged')}, loosened['observed_sequences'])
    else:
        add(4,{'head_removal_observed':first_head is not None,'loosening_observed':bool(loosen),
               'ordered_increments':len(loosen)==len(expected) and all(loosening_value(r['input'],e) for r,e in zip(loosen,expected))},[r['seq'] for r in loosen])
    old=performed('remove',lambda a:a.get('part_id') in role_ids('gasket_old'))
    installed_gaskets=performed('install',lambda a:a.get('part_id')==final['gasket'].get('active_id'))
    closure=max((r['seq'] for r in installed_gaskets),default=None)
    lower=max([r['seq'] for r in old+removed_heads],default=None)
    cleans=performed('clean')
    clean_checks={'old_head_and_gasket_removed':bool(old) and bool(removed_heads)}
    for target in ('head_face','block_deck'):
        clean_checks[target+'_cleaned_before_gasket']=any(r['input'].get('target')==target and lower is not None and closure is not None and lower<r['seq']<closure for r in cleans)
        clean_checks[target+'_clean_final']=all(items.get('surface/'+target+'/'+f) is True for f in ('residue_fraction','dry','debris_count','damaged'))
    add(5,clean_checks,[r['seq'] for r in old+removed_heads+cleans+installed_gaskets])
    installed_heads=performed('install',lambda a:a.get('part_id') in heads)
    head_install=min((r['seq'] for r in installed_heads),default=None)
    services=[r for r in successful if r['name'] in ('machine_head','replace') and r['input'].get('part_id') in heads
              and head_install is not None and r['seq']<head_install]
    flat_checks={}
    limits=config['policy'].get('flatness_limits_m',{})
    measurements=performed('measure',lambda a:a.get('kind')=='flatness')
    for target in ('head_face','block_deck'):
        values=[r for r in measurements if r['input'].get('target')==target and head_install is not None and r['seq']<head_install]
        decision=min((r['seq'] for r in services),default=head_install) if target=='head_face' else head_install
        before=max((r for r in values if decision is not None and r['seq']<decision),key=lambda r:r['seq'],default=None)
        after=max(values,key=lambda r:r['seq'],default=None)
        observed={} if before is None else before['result'].get('observation',{})
        latest={} if after is None else after['result'].get('observation',{})
        limit=limits.get(target)
        needs_recovery=finite(observed.get('value')) and finite(limit) and observed['value']>limit
        recovered=target=='head_face' and bool(services) and after is not None and after['seq']>max(r['seq'] for r in services)
        flat_checks[target+'_measured_before_decision']=observed.get('unit')=='m' and finite(observed.get('value')) and observed['value']>=0
        flat_checks[target+'_correct_decision']=(recovered if needs_recovery else not services or target!='head_face')
        flat_checks[target+'_within_limit']=finite(limit) and limit>0 and latest.get('unit')=='m' and finite(latest.get('value')) and 0<=latest['value']<=limit and finite(final['surfaces'][target].get('warpage_m')) and 0<=final['surfaces'][target]['warpage_m']<=limit
    add(6,flat_checks,[r['seq'] for r in measurements+services+installed_heads])
    measured=performed('measure',lambda a:a.get('kind')=='bolt_stretch')
    bolt_checks={}
    for bolt in bolts:
        pos=bolt['service_position'];body=bolt['body_id']
        decisions=[r for r in successful if r['name'] in ('replace','install') and r['input'].get('part_id')==pos
                   or r['name']=='install' and r['input'].get('part_id')==body]
        decision=min((r['seq'] for r in decisions),default=None)
        observation=max((r for r in measured if r['input'].get('target')==pos and decision is not None and r['seq']<decision),key=lambda r:r['seq'],default=None)
        value={} if observation is None else observation['result'].get('observation',{})
        stretch=value.get('value');limit=config['policy']['stretch_replace_limit_mm']
        bolt_checks[pos+'_measured_before_correct_decision']=(value.get('unit')=='mm' and finite(stretch) and stretch>=0
            and bolt['checks']['bolt_condition'] is True and body is not None and ((body!=pos) if stretch>limit else (body==pos)))
    add(7,bolt_checks,[r['seq'] for r in measured])
    gasket=final['gasket'];active=gasket.get('active_id');catalog=parts.get(active,{}).get('catalog',{})
    dowels=[p for p,v in parts.items() if 'dowel' in v['role']]
    add(8,{'new_selected_gasket':active in role_ids('gasket_new') and items.get('gasket/type') is True,
           'stock_dimensions':catalog.get('bore_mm')==75 and catalog.get('compressed_thickness_mm')==0.762,
           'orientation':items.get('gasket/orientation') is True,
           'retained_dowels_present':bool(dowels) and all(final['parts'][p]['location']=='assembly' for p in dowels),
           'discrete_alignment':gasket.get('dowels_aligned') is True},[r['seq'] for r in installed_gaskets])
    for number,fields in ((9,('first_stage_value','first_stage_sequence')),(10,('final_stage_value','final_stage_sequence','stage_order'))):
        add(number,{b['service_position']+'/'+f:b['checks'][f] is True for b in bolts for f in fields},
            [s['sequence'] for b in bolts for s in b['stages'] if s is not None])
    original_belt=next(p for p in belts if not parts[p].get('replacement_for'))
    belt=final.get('service_replacements',{}).get(original_belt,original_belt)
    installs=performed('install',lambda a:a.get('part_id')==belt)
    tensions=performed('tension_belt',lambda a:a.get('part_id')==belt)
    last_install=max((r['seq'] for r in installs),default=0)
    last_tension=max((r['seq'] for r in tensions),default=0)
    changes=[r['seq'] for r in successful if r['name']=='set_timing' or r['name'] in ('remove','replace','install','tension_belt') and r['input'].get('part_id') in belts]
    last_change=max(changes,default=0)
    post=max((r for r in performed('check_timing') if r['seq']>last_change),key=lambda r:r['seq'],default=None)
    turns=max((r['input']['crank_revolutions'] for r in reference['actions'] if r['name']=='check_timing'),default=0)
    selected=next(v for v in config['variants'] if v['id']==config['variant_id'])
    add(11,{'belt_installed':last_install>0 and final['parts'][belt]['location']=='assembly',
            'current_tension':last_tension>last_install and final['timing'].get('tensioned') is True and final['timing'].get('belt_tensioned') is True,
            'final_marks':items.get('timing/marks_aligned') is True,
            'later_check':post is not None and post['result'].get('observation',{}).get('marks_align') is True and finite(post['input'].get('crank_revolutions')) and post['input']['crank_revolutions']>=turns,
            'worn_belt_replaced':not selected.get('worn_timing_belt') or belt!=original_belt},
            [r['seq'] for r in installs+tensions+([] if post is None else [post])])
    restore={k:v is True for k,v in items.items() if k.startswith('part/') or k.startswith('fastener/') and k.endswith('/final_torque')}
    restore['all_head_fasteners_present']=all(b['body_id'] is not None for b in bolts)
    restore['attachment_history_join']=attachments is not None and attachments['history_matches'] is True and attachments['states_match_history'] is True
    restore['no_outstanding_attachments']=attachments is not None and not attachments['outstanding_release_ids']
    old_gaskets=[p for p,v in parts.items() if v['role'] in ('gasket_old','cover_gasket_old')]
    cover_assessment = cover_gasket_assessment(config, rows, final) if amendment else None
    if amendment:
        head_old = [p for p,v in parts.items() if v['role']=='gasket_old']
        restore['old_head_gasket_discarded'] = len(head_old)==1 and final['parts'][head_old[0]]['location']=='waste'
        restore['accepted_cover_gasket_route'] = cover_assessment['passed']
    else:
        restore['both_old_gaskets_discarded']=len(old_gaskets)==2 and all(final['parts'][p]['location']=='waste' for p in old_gaskets)
        restore['new_cover_gasket']=any(v['role']=='cover_gasket_new' and final['parts'][p]['location']=='assembly' for p,v in parts.items())
    reassembly=config['benchmark_removal'].get('reassembly')
    restore['v2_checklist_present']=reassembly is not None
    if reassembly is not None:
        bindings=dict(config['benchmark_removal']['source_to_body'])
        bindings.update(final['benchmark_removal'].get('replacements',{}))
        bindings['gasket_old']=active
        cover=next((p for p,v in parts.items() if v['role']=='cover_gasket_new' and final['parts'][p]['location']=='assembly'),None)
        bindings['valve_cover_gasket_old']=cover_assessment['active_id'] if amendment else cover
        for obligation in reassembly['requirements']:
            source=obligation['original_id'];body=bindings.get(source)
            restored=body in final['parts'] and final['parts'][body]['location']=='assembly'
            if obligation['original_may_be_reinstalled'] is False:
                if amendment and source=='valve_cover_gasket_old':
                    restored=restored and cover_assessment['passed']
                else:
                    restored=restored and body!=config['benchmark_removal']['source_to_body'][source]
            if amendment and source in ('gasket_old','valve_cover_gasket_old'):
                if source=='gasket_old':
                    evidence={'new':body!=config['benchmark_removal']['source_to_body'][source],
                              'approved':parts.get(body,{}).get('role')=='gasket_new'}
                else:
                    evidence={'new':cover_assessment['route']=='new',
                        'approved':cover_assessment['new_replacement_valid'],
                        'original':cover_assessment['route']=='original_reuse',
                        'inspected':cover_assessment['inspection_valid'],
                        'serviceable':cover_assessment['refit_valid'],
                        'sealant_applied':cover_assessment['treatment_valid']}
                allowed=replacement_allowed(obligation,evidence)
                restore['source_replacement/'+source]=allowed
                restored=restored and allowed
            restore['source_position/'+source]=restored
    add(12,restore,[r['seq'] for r in performed('install')+performed('restore_attachment')])
    earned=sum(r['weight'] for r in output if r['passed']);full=int(all(r['passed'] for r in output))
    return {'schema':'hgj/repair-checkpoints/v1','definition':'CHECKPOINTS-SIGNOFF.md 2026-10-09' + (' Amendment 1' if amendment else ''),
            'total_points':18,'points_earned':earned,'S_full':full,'S_partial':0.5*(earned/18)+0.5*full,
            'checkpoints':output,'scope':'Signed discrete procedure checkpoints; basis labels do not imply physical qualification'}
