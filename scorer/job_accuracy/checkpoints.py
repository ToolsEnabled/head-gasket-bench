"""The study's twelve binary checkpoints and unchanged 18-point formula.

Checks consume actions and final observations. Missing evidence fails a binary
checkpoint with an explicit reason; a successful tool response alone never
supplies an absent mechanical observation. The signed interpretation separates
historical process checks from recoverable final-state checks. Runtime source
authentication and the signed contract's external provenance remain receiving
responsibilities.
"""
from .independent import assess, check, equal, finite, fingerprint, torque_equal, public_body_map, effective_role

DEFINITIONS = (
    ('CP01', 1, 'Torque values, stages and sequence looked up before tightening'),
    ('CP02', 2, 'Valid disassembly with no blocked removal attempt'),
    ('CP03', 1, 'Cylinder 1 at TDC and timing marks aligned before belt removal'),
    ('CP04', 1, 'Head bolts loosened in the specified order and stages'),
    ('CP05', 1, 'Head and old gasket removed and both surfaces cleaned'),
    ('CP06', 1, 'Head and block flatness measured with the correct service decision'),
    ('CP07', 1, 'Head bolts measured with the correct reuse decision'),
    ('CP08', 2, 'Correct new gasket and orientation on aligned dowels'),
    ('CP09', 2, 'Stage 1 torque correct on all ten bolts in sequence'),
    ('CP10', 2, 'Final torque correct on all ten bolts in sequence'),
    ('CP11', 2, 'Timing restored with fitted and tensioned belt'),
    ('CP12', 2, 'Reassembly complete with all required fasteners'),
)


def checkpoint_pass(ident, requirements):
    return bool(requirements) and all(value is True for value in requirements.values())


def same_loosening(actual, expected):
    keys={'part_id','mode','angle_deg'}
    return len(actual)==len(expected) and all(set(a)==set(b)==keys
        and a['part_id']==b['part_id'] and a['mode']==b['mode']=='loosen'
        and finite(a['angle_deg']) and finite(b['angle_deg']) and a['angle_deg']==b['angle_deg']
        for a,b in zip(actual,expected))


def weighted_score(checkpoints):
    """Require exactly the declared binary checks; never change the denominator."""
    check(type(checkpoints) is list and len(checkpoints) == 12
          and [r.get('id') for r in checkpoints] == [r[0] for r in DEFINITIONS], 'checkpoint-census')
    check(all(type(row.get('passed')) is bool and type(row.get('weight')) is int
              and row['weight'] == definition[1] for row, definition in zip(checkpoints, DEFINITIONS)),
          'checkpoint-values')
    earned = sum(row['weight'] for row in checkpoints if row['passed'])
    full = int(all(row['passed'] for row in checkpoints))
    return {'total_points':18, 'points_earned':earned, 'S_full':full,
            'S_partial':0.5*(earned/18)+0.5*full, 'checkpoints':checkpoints}


def evaluate(record, reference, secondary, *, checkpoint_revision='signoff-20261009'):
    from .checkpoint_contracts import selected_revision,AMENDMENT1,AMENDMENT2,documented_loosening
    selected_revision(checkpoint_revision)
    check(secondary.get('checkpoint_revision','signoff-20261009')==checkpoint_revision,'checkpoint-secondary-version')
    config, final = record['config'], record['final_state']
    parts = {p['id']:p for p in config['geometry']['parts']}
    fasteners = {f['id']:f for f in config['geometry']['fasteners']}
    actions = record['actions']; history = final['action_history']
    bodies = {pid:pid for pid in fasteners}
    public = public_body_map(config)
    def args(row):
        value = row['input'] if type(row.get('input')) is dict else {}
        return {k:public.get(v,v) if k in ('target','part_id','replacement_id') and type(v) is str else v
                for k,v in value.items()}
    successful = [row for row in actions if row['result']['ok'] is True]
    def role_ids(role): return {pid for pid,p in parts.items() if effective_role(p)==role}
    head = role_ids('head'); belts = role_ids('timing_belt')
    original_head = {pid for pid,f in fasteners.items() if f['group']=='head' and f.get('service_required',True)}
    observations = {}
    def record_check(index, requirements, sequences=()):
        observations[index] = {'requirements':requirements, 'evidence_sequences':sorted(set(sequences))}
    def performed(name, predicate): return [r for r in successful if r['name']==name and predicate(args(r))]
    first_torque = min((r['seq'] for r in history if r['name']=='torque'
                        and r['input'].get('mode')=='tighten'
                        and r['input'].get('part_id') in role_ids('head_bolt')), default=None)
    seen=set(); search_sequences=[]
    for row in successful:
        if row['name']=='search_service_info' and (first_torque is None or row['seq']<first_torque):
            seen.update(e['id'] for e in row['result'].get('entries',[]));search_sequences.append(row['seq'])
    needed=config['repair_scoring']['lookup_categories']
    record_check(1, {'head_tightening_observed':first_torque is not None,
                    'torque_stages_lookup':bool(needed.get('torque')) and set(needed['torque'])<=seen,
                    'sequence_lookup':bool(needed.get('sequence')) and set(needed['sequence'])<=seen},search_sequences)

    installed={pid for pid,p in parts.items() if p['installed']};blocked=[];removal_sequences=[]
    for row in actions:
        a=args(row);pid=a.get('part_id');ok=row['result']['ok']
        if row['name']=='remove' and pid in parts:
            carried=set(parts[pid].get('carried_body_ids',[]));moving={pid,*carried}
            predecessors=set(parts[pid]['requires_removed'])
            blockers=[p for p in installed if p not in moving and (p in predecessors or bodies.get(p) in predecessors)]
            holders=[p for p in installed if p not in moving and p in bodies
                     and moving.intersection(fasteners[bodies[p]]['holds'])]
            if blockers or holders:blocked.append(row['seq'])
            if ok:installed.difference_update(moving);removal_sequences.append(row['seq'])
        elif row['name']=='install' and ok and pid in parts:
            installed.update({pid,*parts[pid].get('carried_body_ids',[])})
        elif row['name']=='replace' and ok:
            if pid in bodies:bodies[a['replacement_id']]=bodies[pid]
            installed.discard(pid)
    source_removal=secondary['source_removal']
    if source_removal['available']:
        blocked=[row['sequence'] for row in source_removal['disassembly_invalid_attempts']]
    refused_removals=([row['sequence'] for row in source_removal['disassembly_invalid_attempts'] if row['name']=='remove' and not row['ok']]
                      if source_removal['available'] else
                      [row['seq'] for row in actions if row['name']=='remove' and row['result']['ok'] is False])
    record_check(2,{'disassembly_observed':bool(removal_sequences),'no_blocked_removal_attempt':not blocked,
                    'no_refused_removal_attempt':not refused_removals,
                    'source_policy_replay':not source_removal['available'] or source_removal['valid_disassembly']},removal_sequences+blocked+refused_removals)
    belt_removals=performed('remove',lambda a:a.get('part_id') in belts)
    prechecks=[r for r in successful if r['name']=='check_timing' and belt_removals and r['seq']<min(x['seq'] for x in belt_removals)]
    # These are actual observation fields, not truth flags supplied by a scorer.
    latest_precheck=max(prechecks,key=lambda r:r['seq'],default=None)
    tdc=[r for r in ([latest_precheck] if latest_precheck is not None else []) if type(r['result'].get('observation',{}).get('tdc_cylinder')) is int
         and r['result']['observation']['tdc_cylinder']==1
         and r['result']['observation'].get('marks_align') is True]
    first_belt_removal=min((r['seq'] for r in belt_removals),default=None)
    setups=[r for r in successful if r['name']=='set_timing' and first_belt_removal is not None and r['seq']<first_belt_removal]
    latest_setup=max(setups,key=lambda r:r['seq'],default=None)
    setup_valid=latest_setup is not None and latest_precheck is not None and latest_setup['seq']<latest_precheck['seq'] and all(finite(args(latest_setup).get(k)) and args(latest_setup)[k]==0 for k in ('cam_phase_deg','crank_phase_deg'))
    record_check(3,{'belt_removal_observed':bool(belt_removals),'prior_cylinder_1_tdc_and_marks_observed':bool(tdc),
                    'explicit_benchmark_setup':not config.get('benchmark_task') or setup_valid},[r['seq'] for r in tdc+belt_removals+setups])
    first_head_removal=min((r['seq'] for r in performed('remove',lambda a:a.get('part_id') in head)),default=None)
    loosen=[r for r in history if first_head_removal is not None and r['seq']<first_head_removal and r['name']=='torque' and r['input'].get('part_id') in original_head and r['input'].get('mode')=='loosen']
    reference_head_removal=min((r['seq'] for r in reference['actions'] if r['name']=='remove' and r['input'].get('part_id') in head),default=None)
    expected=[r for r in reference['actions'] if reference_head_removal is not None and r['seq']<reference_head_removal and r['name']=='torque' and r['input'].get('part_id') in original_head and r['input'].get('mode')=='loosen']
    actual_inputs=[r['input'] for r in loosen];expected_inputs=[r['input'] for r in expected]
    order_matches=(documented_loosening(actual_inputs,expected_inputs,fasteners,same_loosening,consistent=checkpoint_revision==AMENDMENT2)
                   if checkpoint_revision in (AMENDMENT1,AMENDMENT2) else same_loosening(actual_inputs,expected_inputs))
    record_check(4,{'loosening_observed':bool(loosen),'order_and_increment':order_matches},[r['seq'] for r in loosen])
    removed_head=performed('remove',lambda a:a.get('part_id') in head)
    old_ids=role_ids('gasket_old')|{pid for pid,p in parts.items() if p['role']=='head_gasket' and p['installed']}
    old_removed=performed('remove',lambda a:a.get('part_id') in old_ids)
    cleaned=performed('clean',lambda a:a.get('target') in ('head_face','block_deck'))
    placements=performed('install',lambda a:a.get('part_id')==final['gasket'].get('active_id')
                         and a.get('part_id') in role_ids('gasket_new')|role_ids('gasket_wrong'))
    placement=max((r['seq'] for r in placements),default=None)
    prior_head=[r for r in removed_head if placement is not None and r['seq']<placement]
    prior_old=[r for r in old_removed if placement is not None and r['seq']<placement]
    preparation_start=max((r['seq'] for r in prior_head+prior_old),default=None)
    prep={r['item']:r['correct'] for r in secondary['checklist_accuracy']['items']}
    record_check(5,{'head_removed':bool(removed_head),'old_gasket_removed':bool(old_removed),
                    'both_cleaned_before_closure':all(any(args(r).get('target')==target and prior_old and prior_head
                        and preparation_start is not None and placement is not None
                        and preparation_start<r['seq']<placement
                        for r in cleaned) for target in ('head_face','block_deck')),
                    'clean_final_surfaces':all(prep.get('surface/'+target+'/'+field) is True
                         for target in ('head_face','block_deck') for field in ('residue_fraction','dry','debris_count','damaged'))},
                    [r['seq'] for r in removed_head+old_removed+cleaned+placements])
    # Numeric limits must be provided by the frozen host policy with source IDs;
    # neither parsing prose nor the reference's final value invents a limit.
    flatness=config['policy'].get('flatness_limits_m',{});flatness_sources=config['policy'].get('flatness_limit_source_ids',[])
    flat_rows=performed('measure',lambda a:a.get('kind')=='flatness')
    flat_requirements={'declared_sourced_limits':bool(flatness_sources) and all(s in config['service']['sources'] for s in flatness_sources)}
    head_install=min((r['seq'] for r in performed('install',lambda a:a.get('part_id') in head)),default=None)
    for target in ('head_face','block_deck'):
        measures=[r for r in flat_rows if args(r).get('target')==target and head_install is not None and r['seq']<head_install]
        remedies=([r for r in successful if head_install is not None and r['seq']<head_install
                   and (r['name']=='machine_head' and args(r).get('part_id') in head
                        or r['name']=='replace' and args(r).get('part_id') in head)] if target=='head_face' else [])
        decision=min((r['seq'] for r in remedies),default=head_install)
        prior=[r for r in measures if decision is not None and r['seq']<decision]
        initial=max(prior,key=lambda r:r['seq'],default=None)
        latest=max(measures,key=lambda r:r['seq'],default=None)
        before={} if initial is None else initial['result'].get('observation',{})
        after={} if latest is None else latest['result'].get('observation',{})
        limit=flatness.get(target);final_value=final['surfaces'].get(target,{}).get('warpage_m')
        valid_before=finite(before.get('value')) and before.get('unit')=='m' and before['value']>=0
        valid_after=finite(after.get('value')) and after.get('unit')=='m' and after['value']>=0
        declared=finite(limit) and limit>0
        accepted=config.get('benchmark_task',{}).get('accepted_head_recovery',[])
        recovery=(target=='head_face' and bool(remedies) and all(r['name'] in accepted for r in remedies)
                  and latest is not None and latest['seq']>max(r['seq'] for r in remedies))
        appropriate=(valid_before and declared and (recovery if before['value']>limit else not remedies))
        flat_requirements[target+'_measured_and_within_limit']=(declared and valid_after and after['value']<=limit
            and finite(final_value) and 0<=final_value<=limit)
        flat_requirements[target+'_measurement_before_correct_decision']=appropriate
    record_check(6,flat_requirements,[r['seq'] for r in flat_rows])
    measures=performed('measure',lambda a:a.get('kind')=='bolt_stretch')
    bolt_requirements={}
    for bolt in secondary['bolt_accuracy']['bolts']:
        position=bolt['service_position']
        decisions=performed('replace',lambda a:a.get('part_id')==position)
        decisions+=performed('install',lambda a:a.get('part_id') in (position,bolt['body_id']))
        decision=min((r['seq'] for r in decisions),default=None)
        measure=[r for r in measures if args(r).get('target')==position and decision is not None and r['seq']<decision]
        latest=max(measure,key=lambda r:r['seq'],default=None);obs={} if latest is None else latest['result'].get('observation',{})
        value=obs.get('value');limit=config['policy']['stretch_replace_limit_mm'];stage=bolt['stages'][0]
        bolt_requirements[position+'_measurement_and_decision']=(finite(value) and value>=0 and obs.get('unit')=='mm'
            and stage is not None and decision is not None and latest['seq']<decision<=stage['sequence'] and bolt['checks']['bolt_condition'] is True
            and (value<=limit and bolt['body_id']==position or value>limit and bolt['body_id']!=position))
    record_check(7,bolt_requirements,[r['seq'] for r in measures])
    gasket=final['gasket'];new_gaskets=role_ids('gasket_new');dowels={p for p,v in parts.items() if 'dowel' in v['role']}
    catalog=parts.get(gasket.get('active_id'),{}).get('catalog',{})
    stock_matches=finite(catalog.get('bore_mm')) and catalog['bore_mm']==75 and finite(catalog.get('compressed_thickness_mm')) and catalog['compressed_thickness_mm']==0.762 and catalog.get('construction')=='multilayer steel'
    record_check(8,{'specified_stock_dimensions_and_construction':stock_matches,'correct_new_gasket':gasket.get('active_id') in new_gaskets and prep.get('gasket/type') is True,
                    'correct_orientation':prep.get('gasket/orientation') is True,
                    'dowels_present':bool(dowels) and all(final['parts'][p]['location']=='assembly' for p in dowels),
                    'gasket_dowel_alignment_observed':gasket.get('dowels_aligned') is True},
                    [r['seq'] for r in performed('install',lambda a:a.get('part_id') in new_gaskets)])
    bolts=secondary['bolt_accuracy']['bolts']
    for index,stage,fields in ((9,0,('first_stage_value','first_stage_sequence')),(10,1,('final_stage_value','final_stage_sequence','stage_order'))):
        record_check(index,{b['service_position']+'_'+field:b['checks'][field] is True for b in bolts for field in fields},
                     [b['stages'][stage]['sequence'] for b in bolts if b['stages'][stage] is not None])
    origins={pid for pid in belts if parts[pid].get('replacement_for') is None}
    active_belts={secondary['component_service_positions'].get(pid,pid) for pid in origins}
    belt_installs=performed('install',lambda a:a.get('part_id') in active_belts)
    variant=next(v for v in config['variants'] if v['id']==config['variant_id'])
    belt_needed=variant.get('worn_timing_belt',False)
    replacements=performed('replace',lambda a:a.get('part_id') in belts and a.get('replacement_id') in belts)
    latest_install=max((r['seq'] for r in belt_installs),default=None)
    tensions=performed('tension_belt',lambda a:a.get('part_id') in active_belts)
    latest_tension=max((r['seq'] for r in tensions),default=None)
    changes=[r['seq'] for r in successful if r['name']=='set_timing' or r['name'] in ('remove','replace','install','tension_belt') and args(r).get('part_id') in belts]
    latest_change=max(changes,default=0)
    postchecks=[r for r in successful if r['name']=='check_timing' and latest_install is not None and r['seq']>latest_change]
    latest_postcheck=max(postchecks,key=lambda r:r['seq'],default=None)
    sufficient_turns=max((r['input']['crank_revolutions'] for r in reference['actions'] if r['name']=='check_timing'),default=None)
    timing=final['timing'];benchmark=bool(config.get('benchmark_task'))
    current_tension=(latest_install is not None and latest_tension is not None and latest_tension>latest_install
        and type(timing.get('tensioned_seq')) is int and timing['tensioned_seq']==latest_tension
        and type(timing.get('installed_seq')) is int and timing['installed_seq']==latest_install
        and timing.get('belt_id') in active_belts and timing.get('tensioned') is True)
    record_check(11,{'belt_fitted':bool(belt_installs) and len(active_belts)==1 and all(final['parts'][p]['location']=='assembly' for p in active_belts),
                     'marks_aligned':prep.get('timing/marks_aligned') is True,
                     'check_after_current_installation':prep.get('timing/check_completed') is True,
                     'latest_check_marks_align':latest_postcheck is not None and latest_postcheck['result'].get('observation',{}).get('marks_align') is True,
                     'latest_check_sufficient_rotation':latest_postcheck is not None and finite(args(latest_postcheck).get('crank_revolutions')) and args(latest_postcheck)['crank_revolutions']>=sufficient_turns,
                     'tension_observed':timing.get('belt_tensioned') is True,
                     'current_benchmark_tension_event':not benchmark or current_tension,
                     'worn_belt_replaced':belt_needed is False or bool(replacements) and all(p not in origins for p in active_belts)},[r['seq'] for r in belt_installs+replacements+tensions+postchecks])
    # Required disposable/replaced parts follow the reference disposition; they
    # must not be put back merely to satisfy literal part-ID equality.
    restoration={row['item']:row['correct'] is True for row in secondary['checklist_accuracy']['items']
                 if row['item'].startswith('part/') and not row['item'].endswith('/undamaged')
                 or row['item'].startswith('fastener/') and row['item'].endswith('/final_torque')}
    old_covers=role_ids('cover_gasket_old');new_covers=role_ids('cover_gasket_new')
    restoration['both_gaskets_new']=(bool(old_ids) and bool(old_covers) and all(final['parts'][p]['location']=='waste' for p in old_ids|old_covers)
        and gasket.get('active_id') in role_ids('gasket_new')|role_ids('gasket_wrong')
        and any(final['parts'][p]['location']=='assembly' for p in new_covers))
    if checkpoint_revision in (AMENDMENT1,AMENDMENT2):
        del restoration['both_gaskets_new']
        restoration['new_head_gasket']=(bool(old_ids) and all(final['parts'][p]['location']=='waste' for p in old_ids)
            and gasket.get('active_id') in role_ids('gasket_new')|role_ids('gasket_wrong'))
        restoration.update({row['item']:row['correct'] is True for row in secondary['checklist_accuracy']['items']
                            if row['item'].startswith('service/cover-gasket/') and not row['item'].endswith('/undamaged')})
    restoration['source_positions_and_attachments_restored']=not source_removal['available'] or source_removal['reassembly_complete']
    restoration['all_head_fasteners_present']=all(b['body_id'] is not None for b in bolts)
    record_check(12,restoration,[r['seq'] for r in successful if r['name'] in ('install','replace')])
    rows=[]
    for index,(ident,weight,title) in enumerate(DEFINITIONS,1):
        value=observations[index];requirements=value['requirements']
        rows.append({'id':ident,'title':title,'weight':weight,'passed':checkpoint_pass(ident, requirements),
                     'requirements':requirements,'not_met':[k for k,v in requirements.items() if v is not True],
                     'evidence_sequences':value['evidence_sequences']})
    result=weighted_score(rows)
    result.update(schema='hgj/repair-checkpoints/v1',definition='Study design v2 section 4; CHECKPOINTS-SIGNOFF.md',
                  scope='Binary points for demonstrated procedure checkpoints; absent observations do not earn points',
                  interface_status='Signed checkpoint interpretation; receiving authenticates the run and contract separately')
    if checkpoint_revision in (AMENDMENT1,AMENDMENT2):result['checkpoint_revision']=checkpoint_revision
    return result


def score(record,reference,labor_policy,*,terminal_reason=None,checkpoint_revision='signoff-20261009'):
    secondary=assess(record,reference,labor_policy,terminal_reason=terminal_reason,checkpoint_revision=checkpoint_revision)
    secondary['primary_score']=evaluate(record,reference,secondary,checkpoint_revision=checkpoint_revision)
    producer=record.get('score')
    primary=producer.get('primary_score') if type(producer) is dict else None
    from .comparison import compare_primary
    secondary['primary_comparison']=compare_primary(secondary['primary_score'],primary,DEFINITIONS,len(record['actions']))
    return secondary
