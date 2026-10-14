"""Recompute procedure evidence from values, without the in-game scorer.

The six raw bolt criteria, partial-result treatment and checklist scope are
versioned here. Configuration/reference provenance is a separate receiving
step. The reducer never uses a control's name to determine its mistakes.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math

MAX_ACTIONS = 1024
MAX_PARTS = 2048
SCORER_EPOCH = 'refit-preparation-20261010'
VALUE_TOLERANCE_N_M = 1e-9
WRONG_WORK = frozenset(('wrong_order', 'wrong_torque_value', 'wrong_torque_stage',
                       'wrong_gasket', 'wrong_orientation', 'reused_stretched_bolt',
                       'timing_marks_off', 'redo_work', 'wrong_part', 'wrong_service_decision'))
CLASSIFICATION = 'successful correct work is productive; executed wrong work base is penalty'
CRITERIA = ('bolt_condition', 'first_stage_value', 'final_stage_value',
            'first_stage_sequence', 'final_stage_sequence', 'stage_order')
PREPARATION_FIELDS = ('residue_fraction', 'dry', 'debris_count', 'damaged',
                      'tube_seals_oiled', 'cam_holder_corner_sealant')


class AssessmentInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Independent repair assessment refused: '+code)


def check(condition, code):
    if condition is not True:
        raise AssessmentInputError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False)+'\n').encode()


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def equal(a, b):
    return encoded(a) == encoded(b)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def torque_equal(value, target):
    return finite(value) and finite(target) and abs(value-target) <= VALUE_TOLERANCE_N_M


def observed_torque(value, target):
    return torque_equal(value, target) if finite(value) else None


def all_observed(values):
    values = list(values)
    return False if any(v is False for v in values) else None if any(v is None for v in values) else True


def timing_aligned(timing, tolerance):
    cam, crank = timing.get('cam_phase_deg'), timing.get('crank_phase_deg')
    if not finite(cam) or not finite(crank):
        return None
    return abs((cam-crank/2+180)%360-180) <= tolerance


def blocked_removal(predecessors, holders, turns):
    return bool(predecessors or holders or finite(turns) and turns > 1e-9)


def public_body_map(config):
    """Resolve stock labels from original definitions, before any repair."""
    parts=config['geometry']['parts']; result={}
    for part in parts:
        pid=part['id']
        stock=config['policy'].get('public_observation')=='technician-v2' and (
            part['role'] in ('gasket_new','gasket_wrong')
            or bool(config.get('benchmark_task')) and part['installed'] is False)
        label='stock_'+fingerprint({'body_id':pid,'variant':config['variant_id']})[:12] if stock else pid
        check(label not in result, 'public-alias-census')
        result[label]=pid
    return result


def required_positions(fasteners):
    check(all(type(f.get('service_required',True)) is bool for f in fasteners.values()), 'service-required-domain')
    return {pid for pid,f in fasteners.items() if f.get('service_required',True)}


def effective_role(part):
    return {'head_supply':'head','timing_belt_supply':'timing_belt'}.get(part['role'],part['role'])


def component_bindings(parts, history):
    """Derive current head/belt bodies only from approved exchange events."""
    bindings={}
    for row in history:
        if row['name']!='replace':continue
        a=row['input'];old=a['part_id'];new=a['replacement_id']
        if effective_role(parts[old]) not in ('head','timing_belt'):continue
        origin=parts[old].get('replacement_for',old)
        check(new!=old and parts[new].get('replacement_for')==origin
              and effective_role(parts[new])==effective_role(parts[old])
              and bindings.get(origin,origin)==old, 'component-replacement-position')
        bindings[origin]=new
    return bindings


def attachment_obligations(source_removal):
    """Outstanding discrete releases and contradictory attachment receipts."""
    if not source_removal.get('available'):
        return {'missing': False, 'outstanding_release_ids': [], 'mismatches': []}
    outstanding = sorted(k for k, value in source_removal['final_released'].items() if value is True)
    mismatches = [key for key in source_removal['state_mismatches']
                  if key == 'released' or key.startswith('attachment_history/')]
    return {'missing': bool(outstanding or mismatches), 'outstanding_release_ids': outstanding,
            'mismatches': mismatches}


def metrics(values, final):
    values = list(values)
    correct, unknown = sum(v is True for v in values), sum(v is None for v in values)
    total = len(values)
    observed = 100*correct/total if total and not unknown else None
    return {'correct': correct, 'incorrect': total-correct-unknown, 'unknown': unknown, 'total': total,
            'observed_accuracy_percent': observed, 'final_accuracy_percent': observed if final else None}


def assess(record, reference, labor_policy, *, terminal_reason=None, checkpoint_revision='signoff-20261009'):
    """Assess one committed prefix or finished job against explicit host inputs.

    A terminal reason describes collection, not successful repair completion.
    The producer's score is used only for the disagreement report, never as an
    input to an independent criterion, mistake or charge.
    """
    try:
        from .checkpoint_contracts import selected_revision
        return _assess(record, reference, labor_policy, terminal_reason, selected_revision(checkpoint_revision))
    except AssessmentInputError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        raise AssessmentInputError('malformed-input') from None


def _assess(record, reference, labor_policy, terminal_reason, checkpoint_revision):
    from .checkpoint_contracts import AMENDMENT1,AMENDMENT2,loosening_step,cover_service_evidence
    config, final, actions = record['config'], record['final_state'], record['actions']
    check(type(actions) is list and len(actions) <= MAX_ACTIONS
          and type(record['finished']) is bool and type(reference) is dict
          and (terminal_reason is None or type(terminal_reason) is str and bool(terminal_reason.strip())), 'record-domain')
    check(record['config_sha256'] == fingerprint(config)
          and record['final_state_sha256'] == fingerprint(final), 'record-commitments')
    check(reference['schema'] == 'hgj/repair-reference/v1'
          and reference['geometry_sha256'] == fingerprint(config['geometry'])
          and reference['service_sha256'] == fingerprint(config['service'])
          and reference['variant_id'] == config['variant_id'], 'reference-inputs')
    from .inputs import initial_evidence
    start_evidence = initial_evidence(record, reference)
    parts = {p['id']: p for p in config['geometry']['parts']}
    fasteners = {f['id']: f for f in config['geometry']['fasteners']}
    check(0 < len(parts) == len(config['geometry']['parts']) <= MAX_PARTS
          and len(fasteners) == len(config['geometry']['fasteners'])
          and set(final['parts']) == set(reference['final']['parts']) == set(parts), 'part-census')
    required=required_positions(fasteners)
    head_positions = [p for p, f in fasteners.items() if f['group'] == 'head' and p in required]
    check(len(head_positions) == 10 and len({fasteners[p]['sequence_index'] for p in head_positions}) == 10,
          'head-position-census')
    check(set(reference['stages']) == required and all(type(reference['stages'].get(p)) is list and 1 <= len(reference['stages'][p]) <= 8
              and all(finite(v) and v > 0 for v in reference['stages'][p]) for p in required)
          and all(len(reference['stages'][p]) == 2 for p in head_positions), 'reference-stages')
    check(labor_policy['schema'] == 'hgj/human-time-policy/v1'
          and labor_policy['labor_content_sha256'] == hashlib.sha256(encoded(config['labor'])[:-1]).hexdigest()
          and labor_policy.get('base_classification') in (None, CLASSIFICATION)
          and labor_policy['aggregation'] == 'maximum assessment estimate per action attempt; refused base included once'
          and labor_policy['published_standard'] is False, 'labor-policy')
    rows_for_price = [*labor_policy['actions'].values(), *labor_policy['mistakes'].values(), labor_policy['unknown_action']]
    check(all(type(r['seconds']) is int and 0 <= r['seconds'] <= 86400
              and r['source_ids'] and all(s in labor_policy['sources'] for s in r['source_ids'])
              for r in rows_for_price), 'labor-rows')
    check(all(row['seconds'] > 0 for row in [*labor_policy['actions'].values(), labor_policy['unknown_action']]),
          'labor-action-positive')

    # Resolve the same public stock IDs by their declared deterministic mapping.
    public_to_body = public_body_map(config)
    from .refits import cover_refits
    refit_history = cover_refits(config, record.get('initial_state'), actions) if checkpoint_revision in (AMENDMENT1, AMENDMENT2) else None
    from .removal import replay as replay_removal
    source_removal=replay_removal(config,actions,final)
    source_actions={r['sequence']:r for r in source_removal.get('observations',[])}
    body_position = {p: p for p in fasteners}
    supplied_bolts=config.get('initial_conditions',{}).get('values',{}).get('bolts',{})
    engagement={pid:(supplied_bolts.get(pid,{}).get('turns') if config.get('initial_conditions')
                     else f.get('initial_engagement_turns')) for pid,f in fasteners.items()}
    if start_evidence['available']:
        engagement = {pid: record['initial_state']['bolts'].get(pid, {}).get('turns') for pid in fasteners}
    installed = {p for p, row in parts.items() if row['installed']}
    events = {p: {} for p in fasteners}
    epochs = {p: 0 for p in fasteners}
    orders, group_members = {}, {}
    for group, order in reference['tightening_order'].items():
        group_members[group] = list(dict.fromkeys(order))
        orders[group] = {}
    check(set(group_members) == {fasteners[p]['group'] for p in required}
          and all(set(members) == {p for p, f in fasteners.items() if f['group'] == group and p in required}
                  for group, members in group_members.items()), 'reference-groups')
    repeated, searches = set(), set()
    loosening_count = Counter()
    loosening_candidates=(0,1)
    history, all_mistakes, ledger = [], [], []
    finish_observations = []
    last_drive_change = 0
    timing_checks = []
    sufficient_turns = max((row['input']['crank_revolutions'] for row in reference['actions']
                            if row['name'] == 'check_timing'), default=None)
    check(finite(sufficient_turns) and sufficient_turns > 0, 'reference-timing')
    lookups = config.get('repair_scoring', {}).get('lookup_categories', {})
    relevance = {'wrong_order':'sequence', 'wrong_torque_value':'torque', 'wrong_torque_stage':'torque',
                 'missing_torque_stage':'torque', 'wrong_gasket':'gasket', 'wrong_orientation':'gasket',
                 'reused_stretched_bolt':'bolt_reuse', 'timing_marks_off':'timing'}

    def invalidate(position):
        events[position].clear()
        epochs[position] += 1
        for ordered in orders.get(fasteners[position]['group'],{}).values():
            if position in ordered:
                ordered.remove(position)

    previous = record['config_sha256']
    last_state = None
    finish_seen = False
    for ordinal, action in enumerate(actions, 1):
        check(type(action['seq']) is int and action['seq'] == ordinal
              and type(action['result']['ok']) is bool and action['previous_action_sha256'] == previous
              and (last_state is None or action['pre_state_sha256'] == last_state), 'action-journal')
        previous, last_state = fingerprint(action), action['post_state_sha256']
        name, success = action['name'], action['result']['ok']
        check(not (finish_seen and success), 'successful-action-after-finish')
        if name == 'finish' and success:
            finish_seen = True
        args = deepcopy(action['input']) if type(action['input']) is dict else {}
        for key in ('part_id', 'replacement_id', 'target'):
            if type(args.get(key)) is str:
                args[key] = public_to_body.get(args[key], args[key])
        pid = args.get('part_id', args.get('target'))
        kinds, details = [], {}
        if not success:
            if name == 'remove' and pid in parts:
                predecessors = set(parts[pid]['requires_removed'])
                blockers = [body for body in installed if body in predecessors
                            or body_position.get(body) in predecessors]
                holders = [body for body in installed if body in body_position
                           and pid in fasteners[body_position[body]]['holds']]
                source_block=source_actions.get(ordinal,{})
                blocked=blocked_removal(blockers,holders,engagement.get(pid))
                if source_block.get('source_body_id') is not None:blocked=bool(source_block['reasons'])
                kinds.append('blocked_removal' if blocked else 'invalid_action')
                details.update(installed_predecessors=sorted(blockers), retaining_fasteners=sorted(holders))
                if pid in engagement:details['engagement_turns']=engagement[pid]
            elif not (name == 'search_service_info' and not config['factors']['service_info']):
                kinds.append('invalid_action')
        else:
            history.append({'seq': ordinal, 'name': name, 'input': args})
            if name == 'search_service_info':
                searches.update(row['id'] for row in action['result'].get('entries', []))
            elif name == 'replace':
                if pid in body_position:
                    body_position[args['replacement_id']] = body_position[pid]
                    invalidate(body_position[pid])
                    new=args['replacement_id']
                    engagement[new]=(supplied_bolts.get(new,{}).get('turns') if config.get('initial_conditions') else 0)
                installed.discard(pid)
                if effective_role(parts[pid])=='timing_belt':last_drive_change=ordinal
            elif name in ('remove', 'install'):
                if pid in body_position:
                    invalidate(body_position[pid])
                operation = (name, pid)
                if operation in repeated:
                    kinds.append('redo_work')
                repeated.add(operation)
                moving=source_actions.get(ordinal,{}).get('moving_body_ids') or [pid]
                if name == 'remove':
                    installed.difference_update(moving)
                else:
                    installed.update(moving)
                    if pid in body_position:
                        engagement[pid]=(supplied_bolts.get(pid,{}).get('install_engagement_turns') if config.get('initial_conditions') else 2)
                    if parts[pid]['role'] == 'gasket_wrong':
                        kinds.append('wrong_gasket')
                    if parts[pid]['role'].startswith('gasket_') and args.get('orientation', 'up') != reference['final']['gasket']['orientation']:
                        kinds.append('wrong_orientation')
                    if pid in body_position and fasteners[body_position[pid]]['group'] == 'head':
                        stretch = final['bolts'].get(pid, {}).get('stretch_mm')
                        if finite(stretch) and stretch > config['policy']['stretch_replace_limit_mm']:
                            kinds.append('reused_stretched_bolt')
                    if effective_role(parts[pid]) == 'timing_belt':
                        if timing_aligned(args, config['policy']['timing_tolerance_deg']) is False:
                            kinds.append('timing_marks_off')
                    refit = refit_history['refits'].get(ordinal) if refit_history is not None else None
                    if refit is not None and refit['passed'] is not True:
                        kinds.append('wrong_gasket')
                        details['cover_refit'] = refit
                if effective_role(parts[pid]) == 'timing_belt':
                    last_drive_change = ordinal
            elif name == 'set_timing' or name == 'tension_belt':
                last_drive_change = ordinal
            elif name == 'torque':
                check(body_position.get(pid) in required, 'unserviced-torque-success')
                position = body_position[pid]; group = fasteners[position]['group']
                targets = reference['stages'][position]; members = group_members[group]
                if args['mode'] == 'loosen':
                    old=engagement.get(pid);angle=args.get('angle_deg')
                    engagement[pid]=max(0,old+angle/360) if finite(old) and finite(angle) else None
                    invalidate(position)
                    expected = reference['loosening_order'].get(group, [])
                    rank = loosening_count[group]; loosening_count[group] += 1
                    if rank >= len(expected):
                        kinds.append('redo_work')
                    elif checkpoint_revision in (AMENDMENT1,AMENDMENT2) and group=='head':
                        loosening_candidates,wrong=loosening_step(loosening_candidates,rank,position,fasteners,consistent=checkpoint_revision==AMENDMENT2)
                        if wrong:kinds.append('wrong_order')
                    elif expected[rank] != position:kinds.append('wrong_order')
                else:
                    value = args['value_N_m']
                    later = any(any(stage > 0 for stage in events[p]) for p in members)
                    if position == members[0] and torque_equal(value, targets[0]) and later:
                        for p in members:
                            invalidate(p)
                        kinds.append('redo_work')
                    matching = [stage for stage, target in enumerate(targets) if torque_equal(value, target)]
                    stage = matching[0] if matching else next((stage for stage in range(len(targets))
                        if any(stage not in events[p] for p in members)), len(targets)-1)
                    ordered = orders[group].setdefault(stage, [])
                    if stage in events[position]:
                        kinds.append('redo_work')
                    if position not in ordered:
                        ordered.append(position)
                    rank = ordered.index(position)
                    expected_order = reference['tightening_order'][group][stage*len(members):(stage+1)*len(members)]
                    sequence_ok = rank < len(expected_order) and expected_order[rank] == position
                    stage_ok = all(all(prior in events[p] for p in members) for prior in range(stage))
                    if not sequence_ok: kinds.append('wrong_order')
                    if not torque_equal(value, targets[stage]): kinds.append('wrong_torque_value')
                    if not stage_ok: kinds.append('wrong_torque_stage')
                    events[position][stage] = {'sequence': ordinal, 'value_N_m': value,
                        'sequence_position': rank+1, 'sequence_correct': sequence_ok,
                        'stage_order_correct': stage_ok, 'installation_epoch': epochs[position]}
                    details.update(service_position=position, stage=stage+1, expected_value_N_m=targets[stage])
            elif name == 'check_timing':
                timing_checks.append({'sequence':ordinal, 'turns':args['crank_revolutions']})
            elif name == 'finish':
                from .finish import observe
                observation=observe(config,final,parts,fasteners,history)
                finish_observations.append({'sequence':ordinal,**observation})
                kinds.extend(k for k,v in observation['mistakes'].items() if v is True)
                if observation['mistakes']:
                    details['variant_finish_observations']=observation
                obligations = attachment_obligations(source_removal)
                if obligations['missing']:
                    kinds.append('missing_attachment_restore'); details['attachment_obligations'] = obligations
                missing = [{'position':p, 'stage':stage+1} for p in sorted(required)
                           for stage in range(len(reference['stages'][p])) if stage not in events[p]]
                if missing:
                    kinds.append('missing_torque_stage'); details['missing_stages'] = missing
                if not any(r['sequence'] > last_drive_change and r['turns'] >= sufficient_turns for r in timing_checks):
                    kinds.append('missing_timing_verification')
        kinds = list(dict.fromkeys(kinds))
        categories = sorted({relevance[k] for k in kinds if k in relevance and relevance[k] in lookups
                             and not set(lookups[relevance[k]]) <= searches})
        if categories and config['factors']['service_info']:
            kinds.append('missed_lookup')
        charge = time_charge(labor_policy, name, success, kinds)
        if name=='finish' and success and observation['unknown_types']:
            charge['unobserved_mistake_types']=observation['unknown_types']
            if labor_policy.get('base_classification') == CLASSIFICATION and set(observation['unknown_types']) & WRONG_WORK and not set(kinds) & WRONG_WORK:
                charge['productive_seconds']=None
            charge['penalty_seconds']=None;charge['total_seconds']=None
        ledger.append({'sequence':ordinal, 'action':name, 'ok':success, **charge})
        if kinds:
            all_mistakes.append({'sequence':ordinal, 'types':kinds, 'target':pid, 'detail':details,
                                 'missing_lookup_categories':categories,
                                 'penalty_seconds':charge['penalty_seconds'],
                                 'unpriced_types':charge['unpriced_types']})

    check(equal(history, final['action_history']) and fingerprint(history) == final['identity']['action_history_sha256']
          and (not actions or last_state == fingerprint(final)), 'resolved-history')
    components=component_bindings(parts,history)
    if config.get('benchmark_task'):
        check(equal(components,final.get('service_replacements',{})), 'component-replacement-state')
    finish = any(row['name'] == 'finish' for row in history)
    check(record['finished'] == finish, 'finish-evidence')
    bolts = []
    for position in sorted(head_positions, key=lambda p: fasteners[p]['sequence_index']):
        current = [body for body, pos in body_position.items() if pos == position
                   and final['parts'].get(body, {}).get('location') == 'assembly']
        body = current[0] if len(current) == 1 else None
        bolt = final['bolts'].get(body, {})
        stretch = bolt.get('stretch_mm')
        damage = final['parts'].get(body, {}).get('damaged')
        condition = False if body is None else all_observed([
            None if not finite(stretch) else 0 <= stretch <= config['policy']['stretch_replace_limit_mm'],
            None if type(damage) is not bool else not damage])
        first, second = events[position].get(0), events[position].get(1)
        checks = {'bolt_condition':condition,
                  'first_stage_value': first is not None and torque_equal(first['value_N_m'], reference['stages'][position][0]),
                  'final_stage_value': all_observed([second is not None and torque_equal(second['value_N_m'], reference['stages'][position][1]),
                     observed_torque(bolt.get('torque_N_m'), reference['stages'][position][1])]),
                  'first_stage_sequence':first is not None and first['sequence_correct'],
                  'final_stage_sequence':second is not None and second['sequence_correct'],
                  'stage_order': all(row is not None and row['stage_order_correct'] for row in (first, second))}
        bolts.append({'service_position':position, 'body_id':body,
                      'sequence_index':fasteners[position]['sequence_index'], 'checks':checks,
                      'expected_stages_N_m':list(reference['stages'][position]),
                      'final_observations':{'torque_N_m':bolt.get('torque_N_m'),'stretch_mm':stretch,'damaged':damage},
                      'stages':[first,second], **metrics(checks.values(), finish)})
    cover_service=cover_service_evidence(config,final,actions) if checkpoint_revision in (AMENDMENT1,AMENDMENT2) else None
    items = checklist(reference, final, fasteners, body_position, history, bolts,
                      events, config, last_drive_change, timing_checks, sufficient_turns, components,cover_service)
    known_productive = sum(r['productive_seconds'] for r in ledger if r['productive_seconds'] is not None)
    unallocated_base = sum(r['base_seconds'] for r in ledger if r['productive_seconds'] is None)
    known_penalty = sum(r['known_penalty_seconds'] for r in ledger)
    unpriced = [{'sequence':r['sequence'], 'types':r['unpriced_types']} for r in ledger if r['unpriced_types']]
    unknown_finish = [{'sequence':r['sequence'],'types':r['unknown_types']} for r in finish_observations if r['unknown_types']]
    scope = {'geometry_qualification':config['geometry']['qualification'],
             'geometry_sha256':fingerprint(config['geometry']), 'modeled_parts':len(parts),
             'required_service_fasteners':sorted(required),
             'retained_fasteners_without_stage_requirements':sorted(set(fasteners)-required),
             'dowels':'represented' if any('dowel' in p['role'] for p in parts.values()) else 'not modeled',
             'checklist_coverage':'Modeled-item accuracy; unmodeled service requirements excluded explicitly',
             'not_scored':['Unmodeled service bodies and dowels', 'Real-geometry removal coverage beyond supplied rules',
                           'Flatness and surface-finish applicability beyond the supplied preparation checklist'],
             'runtime_source_authenticated':False}
    result = {'schema':'hgj/independent-repair-assessment/v1', 'record_sha256':fingerprint(record),
              'scorer_epoch':SCORER_EPOCH,
              'reference_sha256':fingerprint(reference), 'labor_policy_sha256':fingerprint(labor_policy),
              'config_sha256':fingerprint(config), 'status':'finished' if finish else 'partial',
              'completion':{'finish_submitted':finish, 'terminal_reason':terminal_reason,
                            'modeled_checklist_complete':all(row['correct'] is True for row in items),
                            'full_service_coverage':False},
              'source_removal':source_removal,
              'initial_evidence':start_evidence,
              'component_service_positions':components,
              'bolt_accuracy':{**metrics((v for b in bolts for v in b['checks'].values()), finish),
                               'criterion_names':list(CRITERIA), 'bolts':bolts},
              'checklist_accuracy':{**metrics((r['correct'] for r in items), finish), 'items':items},
              'mistakes':{'count':len(all_mistakes), 'by_type':dict(sorted(Counter(t for m in all_mistakes for t in m['types']).items())),
                          'events':all_mistakes},
              'finish_observations':finish_observations,
              'human_time':{'productive_seconds':None if unallocated_base else known_productive, 'penalty_seconds':None if unpriced or unknown_finish else known_penalty,
                            'total_seconds':None if unpriced or unknown_finish else known_productive+known_penalty,
                            'known_charged_subtotal_seconds':known_productive+known_penalty+unallocated_base,
                            'base_charge_without_known_allocation_seconds':unallocated_base,
                            'unobserved_finish_mistake_types':unknown_finish,
                            'unpriced_mistakes':unpriced, 'reference_seconds':reference['human_time_seconds'],
                            'qualification':labor_policy['qualification'], 'ledger':ledger},
              'tool_calls':{'attempted':len(actions), 'successful':len(history), 'refused':len(actions)-len(history)},
              'coverage':scope, 'limits':{'action_attempts':MAX_ACTIONS, 'parts':MAX_PARTS},
              'numerical_policy':{'torque_absolute_comparison_tolerance_N_m':VALUE_TOLERANCE_N_M}}
    result['producer_comparison'] = compare_producer(result, record.get('score'))
    if checkpoint_revision in (AMENDMENT1,AMENDMENT2):
        result['checkpoint_revision']=checkpoint_revision
        result['cover_gasket_service']=cover_service
        result['cover_refit_history']=refit_history
    return result


def time_charge(policy, action, successful, labels):
    known = {policy['aliases'].get(label,label) for label in labels}
    unpriced = sorted(label for label in known if label not in policy['mistakes'])
    base = policy['actions'].get(action, policy['unknown_action'])
    wrong = policy.get('base_classification') == CLASSIFICATION and bool(known & WRONG_WORK)
    productive = base['seconds'] if successful and not wrong else 0
    assessment = max((policy['mistakes'][label]['seconds'] for label in known if label in policy['mistakes']), default=0)
    penalty = (base['seconds'] if successful and wrong else 0) + max(0 if successful else base['seconds'], assessment)
    return {'productive_seconds':productive, 'penalty_seconds':None if unpriced else penalty,
            'known_penalty_seconds':penalty, 'total_seconds':None if unpriced else productive+penalty,
            'base_seconds':base['seconds'], 'mistake_types':sorted(known), 'unpriced_types':unpriced,
            'source_ids':sorted(set(base['source_ids']) | {source for label in known if label in policy['mistakes']
                for source in policy['mistakes'][label]['source_ids']})}


def checklist(reference, final, fasteners, body_position, history, bolts, events,
              config, last_drive_change, timing_checks, sufficient_turns, components,cover_service=None):
    rows = []
    def add(item, expected, actual, numeric=False):
        rows.append({'item':item, 'expected':deepcopy(expected), 'actual':deepcopy(actual),
                     'correct':None if actual is None else observed_torque(actual,expected) if numeric else equal(actual,expected)})
    original=reference['final'];parts={p['id']:p for p in config['geometry']['parts']}
    def position(pid):
        p=parts.get(pid,{})
        return p.get('replacement_for',pid) if p.get('role') in ('head','head_supply','timing_belt','timing_belt_supply') else pid
    performed={(r['name'],position(r['input'].get('part_id'))) for r in history}
    needed={(r['name'],position(r['input'].get('part_id'))) for r in reference['actions']}
    for body, state in original['parts'].items():
        part=parts[body]
        if cover_service is not None and body in cover_service['body_ids']:continue
        if config.get('benchmark_task') and effective_role(part) in ('head','timing_belt'):
            origin=position(body);active=components.get(origin,origin)
            if body!=origin:
                if body!=active:add('part/'+body+'/not_installed',True,final['parts'][body]['location']!='assembly')
                continue
            expected_body=reference.get('service_replacements',{}).get(origin,origin)
            add('part/'+origin+'/location',original['parts'][expected_body]['location'],final['parts'][active]['location'])
            if active!=origin:add('part/'+origin+'/replaced_original_disposition','waste',final['parts'][origin]['location'])
            for action in ('remove','install','replace'):
                if (action,origin) in needed:
                    if action=='replace' and effective_role(part)=='head' and set(config['benchmark_task'].get('accepted_head_recovery',[]))>={'replace','machine_head'}:
                        add('part/'+origin+'/service_recovery',True,('replace',origin) in performed or ('machine_head',origin) in performed)
                    else:add('part/'+origin+'/'+action,True,(action,origin) in performed)
            damage=final['parts'][active].get('damaged')
            add('part/'+origin+'/undamaged',True,None if type(damage) is not bool else not damage)
            continue
        if state['location'] in ('supply','unavailable'):
            add('part/'+body+'/not_installed',True,final['parts'][body]['location'] != 'assembly')
        else:
            add('part/'+body+'/location',state['location'],final['parts'][body]['location'])
            for action in ('remove','install','replace'):
                if (action,body) in needed:
                    add('part/'+body+'/'+action,True,(action,body) in performed)
        if state['location'] == 'assembly':
            damage = final['parts'][body].get('damaged')
            add('part/'+body+'/undamaged',True,None if type(damage) is not bool else not damage)
    if cover_service is not None:
        for name,value in cover_service['requirements'].items():add('service/cover-gasket/'+name,True,value)
        body=cover_service['active_body'];damage=final['parts'].get(body,{}).get('damaged')
        add('service/cover-gasket/undamaged',True,None if type(damage) is not bool else not damage)
    for target, surface in original['surfaces'].items():
        for field in PREPARATION_FIELDS:
            if field in surface:
                add('surface/'+target+'/'+field,surface[field],final['surfaces'].get(target,{}).get(field))
    for bolt in bolts:
        pos, body = bolt['service_position'], bolt['body_id']
        expected_body = next(p for p, position in reference['position_by_body'].items()
                             if position == pos and original['parts'][p]['location'] == 'assembly')
        for field in ('thread_clean','thread_oiled','washer_oiled'):
            add('bolt/'+pos+'/'+field,original['bolts'][expected_body][field],final['bolts'].get(body,{}).get(field))
            if body is None:
                rows[-1]['correct'] = False
        for field, value in bolt['checks'].items():
            add('bolt/'+pos+'/'+field,True,value)
            if value is None: rows[-1]['correct'] = None
    add('gasket/type',original['gasket']['type'],final['gasket']['type'])
    add('gasket/orientation',original['gasket']['orientation'],final['gasket']['orientation'])
    add('timing/marks_aligned',True,timing_aligned(final['timing'], config['policy']['timing_tolerance_deg']))
    add('timing/check_completed',True,any(row['sequence'] > last_drive_change and row['turns'] >= sufficient_turns for row in timing_checks))
    for position, fastener in fasteners.items():
        if fastener['group'] == 'head' or fastener.get('service_required',True) is False: continue
        add('fastener/'+position+'/final_torque',original['bolts'][position]['torque_N_m'],final['bolts'][position]['torque_N_m'],True)
        for stage, value in enumerate(reference['stages'][position]):
            observed = events[position].get(stage)
            prefix = 'fastener/'+position+'/stage_'+str(stage+1)+'/'
            add(prefix+'value',value,None if observed is None else observed['value_N_m'],True)
            if observed is None: rows[-1]['correct'] = False
            add(prefix+'sequence',True,observed is not None and observed['sequence_correct'])
            add(prefix+'stage_order',True,observed is not None and observed['stage_order_correct'])
    return rows


def compare_producer(assessment, producer):
    if producer is None:
        return {'status':'unavailable', 'reason':'No procedure score retained', 'disagreements':[]}
    if type(producer) is not dict or producer.get('schema') != 'hgj/repair-score/v1':
        return {'status':'unavailable', 'reason':'No recognized procedure score retained', 'disagreements':[]}
    try:
        return _compare_producer(assessment, producer)
    except (KeyError, TypeError, IndexError, ValueError):
        return {'status':'invalid_producer_score', 'reason':'Producer comparison fields are malformed', 'disagreements':[]}


def _compare_producer(assessment, producer):
    differences = []
    reported = {b['service_position']: b for b in producer['bolt_accuracy']['bolts']}
    for bolt in assessment['bolt_accuracy']['bolts']:
        for field, value in bolt['checks'].items():
            actual = reported.get(bolt['service_position'],{}).get('checks',{}).get(field)
            if not equal(value,actual):
                differences.append({'field':'bolt/'+bolt['service_position']+'/'+field,'independent':value,'producer':actual})
    reported_items = {row['item']:row for row in producer['checklist_accuracy']['items']}
    independent_items = {row['item']:row for row in assessment['checklist_accuracy']['items']}
    for key in sorted(set(reported_items) & set(independent_items)):
        if not equal(reported_items[key]['correct'],independent_items[key]['correct']):
            differences.append({'field':key,'independent':independent_items[key]['correct'],'producer':reported_items[key]['correct']})
    for field in ('productive_seconds','penalty_seconds','total_seconds'):
        if not equal(assessment['human_time'][field],producer['human_time'][field]):
            differences.append({'field':'human_time/'+field,'independent':assessment['human_time'][field],'producer':producer['human_time'][field]})
    if not equal(assessment['mistakes']['by_type'],producer['mistakes']['by_type']):
        differences.append({'field':'mistakes/by_type','independent':assessment['mistakes']['by_type'],'producer':producer['mistakes']['by_type']})
    only_independent = sorted(set(independent_items)-set(reported_items))
    only_producer = sorted(set(reported_items)-set(independent_items))
    return {'status':'disagreement' if differences or only_independent or only_producer else 'agreement',
            'disagreements':differences,'independent_only_items':only_independent,
            'producer_only_items':only_producer,
            'denominators':{'independent':len(independent_items),'producer':len(reported_items)},
            'scope':'Fieldwise comparison; different checklist denominators are never compared as equivalent percentages'}
