"""Deterministic repair procedure scoring from trusted reference and action values.

No engine model, soak, elapsed-time simulation or provider is called here.
The reference is supplied by the trusted run configuration, never by a tool.
"""
import copy
import math
from collections import Counter
from .codec import canonical, digest
from .procedure_actions import effective_role

MODE = 'procedure-accuracy-v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def same(left, right):
    return canonical(left) == canonical(right)


def close(left, right):
    return type(left) in (int, float) and type(right) in (int, float) and math.isfinite(left) and math.isfinite(right) and abs(left-right) <= 1e-9


def mechanical(state):
    return {key: copy.deepcopy(state[key]) for key in ('parts', 'bolts', 'surfaces', 'gasket', 'timing')}


def resolved_actions(records, state):
    successful = {row['seq']: row for row in state['action_history']}
    return [{'seq': row['seq'], 'name': row['name'],
             'input': copy.deepcopy(successful.get(row['seq'], row)['input']),
             'ok': row['result']['ok'], 'result': row['result']}
            for row in records]


def build_reference(config, initial_state, actions, final_state):
    """Capture a reviewed correct script, including source service-position IDs."""
    require(actions and actions[-1]['name'] == 'finish' and all(row['result']['ok'] for row in actions),
            'Reference must be a completed successful procedure')
    rows = resolved_actions(actions, final_state)
    positions = {f['id']: f['id'] for f in config['geometry']['fasteners']}
    groups = {f['id']: f['group'] for f in config['geometry']['fasteners']}
    stages, tightening, loosening = {}, {}, {}
    for row in rows:
        args = row['input']
        if row['name'] == 'replace' and args['part_id'] in positions:
            positions[args['replacement_id']] = positions[args['part_id']]
            groups[args['replacement_id']] = groups[args['part_id']]
        if row['name'] == 'torque':
            pid = positions[args['part_id']]
            group = groups[args['part_id']]
            if args['mode'] == 'tighten':
                stages.setdefault(pid, []).append(args['value_N_m'])
                tightening.setdefault(group, []).append(pid)
            else:
                loosening.setdefault(group, []).append(pid)
    head = [f for f in config['geometry']['fasteners'] if f['group'] == 'head' and f.get('service_required', True)]
    require(len(head) == 10 and all(len(stages.get(f['id'], [])) == 2 for f in head),
            'Reference requires ten head positions and two complete tightening stages')
    result = {
        'schema': 'hgj/repair-reference/v1', 'initial_sha256': digest(mechanical(initial_state)),
        'geometry_sha256': digest(config['geometry']), 'service_sha256': digest(config['service']),
        'variant_id': config['variant_id'], 'final': mechanical(final_state),
        'actions': [{'seq': row['seq'], 'name': row['name'], 'input': row['input']} for row in rows],
        'stages': stages, 'tightening_order': tightening, 'loosening_order': loosening,
        'position_by_body': positions,
        'service_replacements': copy.deepcopy(final_state.get('service_replacements', {})),
        'human_time_seconds': sum(config['labor']['actions'][row['name']]['seconds'] for row in rows),
        'qualification': 'Reviewed scripted reference; source coverage is reported separately',
    }
    from .checkpoints import checkpoint_revision, AMENDMENT_REVISION
    revision = checkpoint_revision(config)
    if revision == AMENDMENT_REVISION:
        result['checkpoint_revision'] = revision
    return result


def validate_reference(config, initial_state):
    settings = config['repair_scoring']
    require(settings.get('mode') == MODE, 'Unknown repair scoring mode')
    reference = settings['reference']
    require(digest(reference) == settings.get('reference_sha256'), 'Repair reference commitment differs')
    require(reference.get('schema') == 'hgj/repair-reference/v1'
            and reference.get('initial_sha256') == digest(mechanical(initial_state))
            and reference.get('geometry_sha256') == digest(config['geometry'])
            and reference.get('service_sha256') == digest(config['service'])
            and reference.get('variant_id') == config['variant_id'],
            'Repair reference differs from source inputs')
    from .checkpoints import checkpoint_revision, ORIGINAL_REVISION
    require(reference.get('checkpoint_revision', ORIGINAL_REVISION) == checkpoint_revision(config),
            'Repair reference checkpoint revision differs')
    require(type(settings.get('lookup_categories', {})) is dict, 'Lookup categories must be a mapping')
    for name, ids in settings.get('lookup_categories', {}).items():
        require(type(name) is str and type(ids) is list and ids
                and all(type(value) is str for value in ids), 'Invalid lookup category')
    return reference


def attachment_obligations(config, initial_state, rows, final_state):
    """Join successful release/restore events to typed final attachment state."""
    spec = config.get('benchmark_removal')
    if spec is None:
        return None
    declared = set(spec['policy']['release_actions'])
    released = dict(initial_state['benchmark_removal']['released'])
    expected_history = []
    touched = set()
    valid_events = set(released) == declared and all(type(v) is bool for v in released.values())
    for row in rows:
        if not row['ok'] or row['name'] not in ('release_attachment', 'restore_attachment'):
            continue
        ident = row['input'].get('release_id')
        if ident not in declared:
            valid_events = False
            continue
        if row['name'] == 'restore_attachment' and released.get(ident) is not True:
            valid_events = False
        released[ident] = row['name'] == 'release_attachment'
        touched.add(ident)
        expected_history.append({'seq':row['seq'], 'action':row['name'], 'release_id':ident})
    current = final_state.get('benchmark_removal', {})
    actual = current.get('released', {})
    history = [{'seq':r.get('seq'), 'action':r.get('action'), 'release_id':r.get('release_id')}
               for r in current.get('attachment_history', [])
               if r.get('action') in ('release_attachment','restore_attachment')]
    history_matches = valid_events and same(history, expected_history)
    states_match = set(actual) == declared and all(type(actual.get(k)) is bool
                   and actual[k] is released.get(k) for k in declared)
    outstanding = sorted(k for k in declared if released.get(k) is not False or actual.get(k) is not False)
    return {'declared_count':len(declared), 'used_release_ids':sorted(touched),
            'outstanding_release_ids':outstanding, 'history_matches':history_matches,
            'states_match_history':states_match,
            'restored_by_id':{k:actual.get(k) is False and released.get(k) is False for k in sorted(declared)},
            'qualification':'Discrete benchmark attachment obligations; replacement bodies retain source service positions'}


def score_repair(config, initial_state, records, final_state, *, _charge_cache=None):
    """Return replay-stable accuracy, mistakes and charged time.

    Real wall time and provider usage belong to a separate measured envelope.
    A successful correction may recover final accuracy; prior mistakes remain.
    """
    from .human_time import charge, MAX_NAME_LENGTH
    reference = validate_reference(config, initial_state)
    policy = config['repair_scoring']['human_time_policy']
    policy_key = digest(policy)
    charge_cache = {} if _charge_cache is None else _charge_cache
    rows = resolved_actions(records, final_state)
    attachments = attachment_obligations(config, initial_state, rows, final_state)
    from .checkpoints import (checkpoint_revision, AMENDMENT_REVISION, loosening_assessment,
                              cover_gasket_assessment, cover_refit_assessments)
    amendment = checkpoint_revision(config) == AMENDMENT_REVISION
    loosened = loosening_assessment(config, initial_state, rows) if amendment else None
    cover_assessment = cover_gasket_assessment(config, rows, final_state) if amendment else None
    cover_refits = cover_refit_assessments(config, initial_state, rows) if amendment else {}
    parts = {part['id']: part for part in config['geometry']['parts']}
    fasteners = {f['id']: f for f in config['geometry']['fasteners']}
    positions = {pid: pid for pid in fasteners}
    locations = {pid: row['location'] for pid, row in initial_state['parts'].items()}
    public = {}
    for pid, part in parts.items():
        label = 'stock_'+digest({'body_id': pid, 'variant': config['variant_id']})[:12] if config['policy'].get('public_observation') == 'technician-v2' and (part['role'] in ('gasket_new', 'gasket_wrong') or (config.get('benchmark_task') and not part['installed'])) else pid
        public[label] = pid
    counts, seen_ops = Counter(), set()
    measured, inspected = set(), set()
    variant_mode = bool(config.get('benchmark_task'))
    mistakes, charges, searches = [], [], set()
    groups = {}
    for group, order in reference['tightening_order'].items():
        members = list(dict.fromkeys(order))
        groups[group] = {'members': members, 'events': {}, 'orders': {}, 'epoch': 0, 'all': []}
    categories = config['repair_scoring'].get('lookup_categories', {})
    relevant = {
        'wrong_torque_value': 'torque', 'wrong_torque_stage': 'torque',
        'missing_torque_stage': 'torque', 'wrong_order': 'sequence',
        'reused_stretched_bolt': 'bolt_reuse', 'timing_marks_off': 'timing',
        'wrong_gasket': 'gasket', 'wrong_orientation': 'gasket',
    }
    completed = any(row['name'] == 'finish' and row['ok'] for row in rows)

    def incident(labels, seq, target=None, detail=None):
        labels = list(dict.fromkeys(labels))
        absent = sorted({relevant[label] for label in labels if label in relevant
                         and relevant[label] in categories and not set(categories[relevant[label]]) <= searches})
        if absent and config['factors']['service_info']:
            labels.append('missed_lookup')
        if labels:
            mistakes.append({'sequence': seq, 'types': labels, 'target': target,
                             'detail': detail or {}, 'missing_lookup_categories': absent})
        return labels

    for row in rows:
        original_name, args, seq, ok = row['name'], row['input'], row['seq'], row['ok']
        name = original_name if type(original_name) is str else ''
        args = args if type(args) is dict else {}
        pid = args.get('part_id', args.get('target'))
        pid = public.get(pid, pid) if type(pid) is str else None
        labels = []
        detail = {}
        if not ok:
            if name == 'remove' and pid in parts:
                blockers = [p for p in parts[positions.get(pid, pid)]['requires_removed']
                            if locations.get(p) == 'assembly']
                holders = [body for body, pos in positions.items()
                           if locations.get(body) == 'assembly' and pid in fasteners[pos]['holds']]
                labels = ['blocked_removal']
                detail = {'installed_predecessors': blockers, 'retaining_fasteners': holders,
                          'refusal': row['result'].get('refusal')}
            elif name == 'search_service_info' and not config['factors']['service_info']:
                detail = {'environmental_refusal': 'Service information disabled by factor'}
            else:
                labels = ['invalid_action']
                detail = {'refusal': row['result'].get('refusal')}
        else:
            if name == 'search_service_info':
                searches.update(entry['id'] for entry in row['result'].get('entries', []))
            if name == 'measure':
                measured.add((pid, args.get('kind')))
            if name == 'inspect':
                inspected.add(pid)
            if name == 'replace' and pid in positions:
                positions[args['replacement_id']] = positions[pid]
            if name == 'replace':
                locations[pid] = 'waste'
                locations[args['replacement_id']] = 'tray'
            if name in ('remove', 'install'):
                if pid in positions:
                    position = positions[pid]
                    group_data = groups.get(fasteners[position]['group'])
                    if group_data is not None:
                        for events in group_data['events'].values():
                            events.pop(position, None)
                        for order in group_data['orders'].values():
                            if position in order:
                                order.remove(position)
                key = (name, pid)
                if key in seen_ops:
                    labels.append('redo_work')
                seen_ops.add(key)
                locations[pid] = ('waste' if parts[pid]['role'] == 'gasket_old' else 'tray') if name == 'remove' else 'assembly'
                if name == 'install':
                    role = effective_role(parts[pid])
                    if role == 'gasket_wrong':
                        labels.append('wrong_gasket')
                    if role.startswith('gasket_') and args.get('orientation', 'up') != reference['final']['gasket']['orientation']:
                        labels.append('wrong_orientation')
                    if pid in positions and fasteners[positions[pid]]['group'] == 'head':
                        bolt = final_state['bolts'].get(pid, initial_state['bolts'].get(pid, {}))
                        stretch = bolt.get('stretch_mm')
                        if type(stretch) in (int, float) and stretch > config['policy']['stretch_replace_limit_mm']:
                            labels.append('reused_stretched_bolt')
                    if role == 'timing_belt':
                        delta = (args['cam_phase_deg'] - args['crank_phase_deg']/2 + 180) % 360 - 180
                        if abs(delta) > config['policy']['timing_tolerance_deg']:
                            labels.append('timing_marks_off')
            if seq in cover_refits and cover_refits[seq]['passed'] is not True:
                labels.append('wrong_gasket')
                detail['cover_refit'] = copy.deepcopy(cover_refits[seq])
            if name == 'torque' and pid in positions:
                pos = positions[pid]
                group = fasteners[pos]['group']
                data = groups[group]
                if args['mode'] == 'loosen':
                    # Releasing a fastener invalidates prior tightening evidence,
                    # even if the body has not yet left its installation position.
                    for events in data['events'].values():
                        events.pop(pos, None)
                    for order in data['orders'].values():
                        if pos in order:
                            order.remove(pos)
                    index = counts[(group, 'loosen')]
                    expected = reference['loosening_order'].get(group, [])
                    if index >= len(expected):
                        labels.append('redo_work')
                    elif amendment and group == 'head':
                        if seq in loosened['order_violation_sequences']:
                            labels.append('wrong_order')
                        if seq in loosened['increment_violation_sequences']:
                            labels.append('wrong_torque_value')
                    elif expected[index] != pos:
                        labels.append('wrong_order')
                    counts[(group, 'loosen')] += 1
                else:
                    expected = reference['stages'][pos]
                    value = args['value_N_m']
                    first_stage = data['events'].get(0, {})
                    later_seen = any(data['events'].get(i) for i in range(1, len(expected)))
                    if close(value, expected[0]) and pos == data['members'][0] and later_seen:
                        data['events'], data['orders'] = {}, {}
                        data['epoch'] += 1
                        labels.append('redo_work')
                        first_stage = {}
                    matches = [i for i, target in enumerate(expected) if close(value, target)]
                    stage = matches[0] if matches else next((i for i in range(len(expected))
                        if len(data['events'].get(i, {})) < len(data['members'])), len(expected)-1)
                    events = data['events'].setdefault(stage, {})
                    order = data['orders'].setdefault(stage, [])
                    correction = pos in events
                    if correction:
                        labels.append('redo_work')
                    else:
                        order.append(pos)
                    rank = order.index(pos)
                    expected_order = reference['tightening_order'][group][stage*len(data['members']):(stage+1)*len(data['members'])]
                    ordered = rank < len(expected_order) and expected_order[rank] == pos
                    stage_ordered = all(set(data['events'].get(prior, {})) == set(data['members']) for prior in range(stage))
                    if not ordered:
                        labels.append('wrong_order')
                    if not close(value, expected[stage]):
                        labels.append('wrong_torque_value')
                    if not stage_ordered:
                        labels.append('wrong_torque_stage')
                    events[pos] = {'sequence': seq, 'value_N_m': value, 'sequence_position': rank+1,
                                   'sequence_correct': ordered, 'stage_order_correct': stage_ordered}
                    data['all'].append({'sequence': seq, 'position': pos, 'stage': stage+1})
                    detail = {'service_position': pos, 'stage': stage+1, 'expected_value_N_m': expected[stage]}
            if name == 'finish':
                if attachments is not None and (attachments['outstanding_release_ids']
                        or not attachments['history_matches'] or not attachments['states_match_history']):
                    labels.append('missing_attachment_restore')
                    detail['attachment_obligations'] = copy.deepcopy(attachments)
                if variant_mode:
                    required_measurements = {('head_face','flatness'), ('block_deck','flatness')}
                    required_measurements.update((key, 'bolt_stretch') for key, f in fasteners.items() if f['group'] == 'head')
                    absent_measurements = sorted(required_measurements - measured)
                    if absent_measurements:
                        labels.append('missed_measurement')
                        detail['missing_measurements'] = absent_measurements
                    belt_original = next(key for key, part in parts.items() if part['role'] == 'timing_belt')
                    belt_active = final_state.get('service_replacements', {}).get(belt_original, belt_original)
                    if belt_original not in inspected:
                        labels.append('missed_inspection')
                    if any(surface['warpage_m'] > config['policy']['flatness_limit_m']
                           for target, surface in final_state['surfaces'].items() if target in ('head_face', 'block_deck')):
                        labels.append('wrong_service_decision')
                    if final_state['parts'][belt_active]['damaged']:
                        labels.append('wrong_part')
                    if final_state['timing'].get('tensioned') is not True:
                        labels.append('missed_belt_tension')
                missing = []
                for group, data in groups.items():
                    for pos in data['members']:
                        for stage in range(len(reference['stages'][pos])):
                            if pos not in data['events'].get(stage, {}):
                                missing.append({'position': pos, 'stage': stage+1})
                if missing:
                    labels.append('missing_torque_stage')
                    detail['missing_stages'] = missing
        labels = incident(labels, seq, pid, detail)
        charged_name = name if name.strip() and len(name) <= MAX_NAME_LENGTH else 'invalid_action'
        cache_key = (policy_key, charged_name, ok, tuple(labels))
        if cache_key not in charge_cache:
            charge_cache[cache_key] = charge(policy, charged_name, ok=ok, mistake_types=labels)
        charged = copy.deepcopy(charge_cache[cache_key])
        charges.append({'sequence': seq, 'action': original_name, 'charged_action': charged_name, 'ok': ok, **charged})
        if labels:
            mistakes[-1]['penalty_seconds'] = charged['penalty_seconds']
            mistakes[-1]['penalties'] = copy.deepcopy(charged['penalties'])

    # Final bolt metrics use the latest corrected value in each active pass.
    bolts = []
    for pos, f in fasteners.items():
        if f['group'] != 'head' or not f.get('service_required', True):
            continue
        candidates = [pid for pid, source in positions.items() if source == pos and final_state['parts'][pid]['location'] == 'assembly']
        body = candidates[0] if len(candidates) == 1 else None
        bolt = final_state['bolts'].get(body, {})
        stretch = bolt.get('stretch_mm')
        condition = body is not None and type(stretch) in (int, float) and stretch <= config['policy']['stretch_replace_limit_mm'] and not final_state['parts'][body]['damaged']
        data = groups['head']
        stages = [data['events'].get(i, {}).get(pos) for i in range(2)]
        checks = {'bolt_condition': condition,
                  'first_stage_value': stages[0] is not None and close(stages[0]['value_N_m'], reference['stages'][pos][0]),
                  'final_stage_value': stages[1] is not None and close(stages[1]['value_N_m'], reference['stages'][pos][1]) and close(bolt.get('torque_N_m'), reference['stages'][pos][1]),
                  'first_stage_sequence': stages[0] is not None and stages[0]['sequence_correct'],
                  'final_stage_sequence': stages[1] is not None and stages[1]['sequence_correct'],
                  'stage_order': all(stage is not None and stage['stage_order_correct'] for stage in stages)}
        bolts.append({'service_position': pos, 'sequence_index': f['sequence_index'], 'body_id': body,
                      'checks': checks, 'stages': copy.deepcopy(stages), 'correct': sum(checks.values()),
                      'total': len(checks), 'accuracy_percent': 100*sum(checks.values())/len(checks)})

    checklist = []
    successful = [row for row in rows if row['ok']]
    def check(key, expected, actual, *, numeric=False):
        passed = close(actual, expected) if numeric else same(actual, expected)
        checklist.append({'item': key, 'expected': expected, 'actual': actual, 'correct': passed})
    if attachments is not None:
        check('attachment/history_matches', True, attachments['history_matches'])
        check('attachment/state_matches_history', True, attachments['states_match_history'])
        for ident, restored in attachments['restored_by_id'].items():
            check('attachment/'+ident+'/restored', True, restored)
    def service_position(pid):
        definition = parts.get(pid, {'role':None})
        return definition.get('replacement_for', pid) if effective_role(definition) in ('head', 'timing_belt') else pid
    expected_ops = {(row['name'], service_position(row['input'].get('part_id')))
                    for row in reference['actions'] if 'part_id' in row['input']}
    actual_ops = {(row['name'], service_position(row['input'].get('part_id')))
                  for row in successful if 'part_id' in row['input']}
    final = reference['final']
    active_replacements = final_state.get('service_replacements', {})
    for pid, expected in final['parts'].items():
        definition = parts[pid]
        if amendment and definition['role'] in ('cover_gasket_old', 'cover_gasket_new'):
            if definition['role'] == 'cover_gasket_new':
                continue
            body = cover_assessment['active_id']
            check('part/'+pid+'/location', 'assembly', final_state['parts'].get(body, {}).get('location'))
            check('part/'+pid+'/accepted_cover_route', True, cover_assessment['passed'])
            continue
        if variant_mode and effective_role(definition) in ('head', 'timing_belt'):
            if definition.get('replacement_for'):
                # Supply use is checked at its original service position.
                continue
            reference_body = reference.get('service_replacements', {}).get(pid, pid)
            body = active_replacements.get(pid, pid)
            check('part/'+pid+'/location', final['parts'][reference_body]['location'], final_state['parts'][body]['location'])
            if body != pid:
                check('part/'+pid+'/replaced_original_disposition', 'waste', final_state['parts'][pid]['location'])
            for action in ('remove', 'install', 'replace'):
                if (action, pid) in expected_ops:
                    check('part/'+pid+'/'+action, True, (action, pid) in actual_ops)
            continue
        if expected['location'] == 'supply':
            check('part/'+pid+'/not_installed', True, final_state['parts'][pid]['location'] != 'assembly')
            continue
        check('part/'+pid+'/location', expected['location'], final_state['parts'][pid]['location'])
        for action in ('remove', 'install', 'replace'):
            if (action, pid) in expected_ops:
                check('part/'+pid+'/'+action, True, (action, pid) in actual_ops)
    for target, expected in final['surfaces'].items():
        for field in ('residue_fraction', 'dry', 'debris_count', 'damaged', 'tube_seals_oiled', 'cam_holder_corner_sealant'):
            if field in expected:
                check('surface/'+target+'/'+field, expected[field], final_state['surfaces'][target].get(field))
    for bolt in bolts:
        body = bolt['body_id']
        expected_body = next((pid for pid, pos in reference['position_by_body'].items()
                              if pos == bolt['service_position'] and final['parts'][pid]['location'] == 'assembly'), None)
        for field in ('thread_clean', 'thread_oiled', 'washer_oiled'):
            check('bolt/'+bolt['service_position']+'/'+field, final['bolts'][expected_body][field],
                  final_state['bolts'].get(body, {}).get(field))
        for key, value in bolt['checks'].items():
            check('bolt/'+bolt['service_position']+'/'+key, True, value)
    check('gasket/type', final['gasket']['type'], final_state['gasket']['type'])
    check('gasket/orientation', final['gasket']['orientation'], final_state['gasket']['orientation'])
    phase = (final_state['timing']['cam_phase_deg']-final_state['timing']['crank_phase_deg']/2+180)%360-180
    check('timing/marks_aligned', True, abs(phase) <= config['policy']['timing_tolerance_deg'])
    expected_turns = [row['input']['crank_revolutions'] for row in reference['actions'] if row['name'] == 'check_timing']
    last_belt_change = max((row['seq'] for row in successful
                            if row['name'] in ('remove', 'install', 'tension_belt')
                            and effective_role(parts.get(row['input'].get('part_id'), {'role':None})) == 'timing_belt'), default=0)
    observed_turns = [row['input']['crank_revolutions'] for row in successful
                      if row['name'] == 'check_timing' and row['seq'] > last_belt_change]
    check('timing/check_completed', True, bool(expected_turns) and any(turns >= expected_turns[-1] for turns in observed_turns))
    if variant_mode:
        first_removal = min((row['seq'] for row in successful if row['name'] == 'remove'
                             and effective_role(parts.get(row['input'].get('part_id'), {'role':None})) == 'timing_belt'), default=0)
        prechecks = [row for row in successful if row['name'] == 'check_timing' and row['seq'] < first_removal]
        setups = [row for row in successful if row['name'] == 'set_timing' and row['seq'] < first_removal
                  and close(row['input']['cam_phase_deg'], 0) and close(row['input']['crank_phase_deg'], 0)]
        check('timing/pre_removal_setup', True, any(setup['seq'] < observed['seq'] for setup in setups for observed in prechecks))
        check('timing/tensioned', True, final_state['timing'].get('tensioned') is True)
        belt_original = next(key for key, part in parts.items() if part['role'] == 'timing_belt')
        belt_active = active_replacements.get(belt_original, belt_original)
        check('timing/belt_condition', False, final_state['parts'][belt_active]['damaged'])
        check('timing/belt_inspected', True, belt_original in inspected)
        for target in ('head_face','block_deck'):
            check('surface/'+target+'/measured', True, (target,'flatness') in measured)
            check('surface/'+target+'/within_service_limit', True, final_state['surfaces'][target]['warpage_m'] <= config['policy']['flatness_limit_m'])
        for pos, f in fasteners.items():
            if f['group'] == 'head':
                check('bolt/'+pos+'/measured', True, (pos,'bolt_stretch') in measured)
    for pos, f in fasteners.items():
        if f['group'] == 'head':
            continue
        check('fastener/'+pos+'/final_torque', final['bolts'][pos]['torque_N_m'], final_state['bolts'][pos].get('torque_N_m'), numeric=True)
        for index, value in enumerate(reference['stages'].get(pos, [])):
            event = groups[f['group']]['events'].get(index, {}).get(pos)
            check('fastener/'+pos+'/stage_'+str(index+1)+'/value', value,
                  None if event is None else event['value_N_m'], numeric=True)
            check('fastener/'+pos+'/stage_'+str(index+1)+'/sequence', True,
                  event is not None and event['sequence_correct'])
            check('fastener/'+pos+'/stage_'+str(index+1)+'/stage_order', True,
                  event is not None and event['stage_order_correct'])
    checklist.sort(key=lambda row:row['item'])
    productive = sum(row['productive_seconds'] for row in charges)
    penalty = sum(row['penalty_seconds'] for row in charges)
    bolt_correct = sum(row['correct'] for row in bolts)
    bolt_total = sum(row['total'] for row in bolts)
    checklist_correct = sum(row['correct'] for row in checklist)
    types = Counter(label for row in mistakes for label in row['types'])
    has_dowels = any('dowel' in part['role'] for part in parts.values())
    result = {
        'schema': 'hgj/repair-score/v1', 'status': 'scored' if completed else 'in_progress',
        'qualification': 'Procedure accuracy against the committed scripted reference',
        'reference_sha256': config['repair_scoring']['reference_sha256'],
        'tool_calls': len(records),
        'human_time': {'productive_seconds': productive, 'penalty_seconds': penalty,
                       'total_seconds': productive+penalty,
                       'reference_seconds': reference['human_time_seconds'], 'ledger': charges,
                       'qualification': config['repair_scoring']['human_time_policy'].get('qualification'),
                       'sources': copy.deepcopy(config['repair_scoring']['human_time_policy'].get('sources', {}))},
        'mistakes': {'count': len(mistakes), 'by_type': dict(sorted(types.items())), 'events': mistakes},
        'bolt_accuracy': {'correct': bolt_correct, 'total': bolt_total,
                          'accuracy_percent': 100*bolt_correct/bolt_total, 'bolts': bolts},
        'checklist_accuracy': {'correct': checklist_correct, 'total': len(checklist),
                              'accuracy_percent': 100*checklist_correct/len(checklist), 'items': checklist},
        'coverage': {'geometry_qualification': config['geometry']['qualification'],
                     'geometry_sha256': digest(config['geometry']),
                     'dowels': ('Source-backed retained-body presence; condition, fit and removal not assessed'
                                if config['geometry'].get('retained_body_source') else
                                'represented in part checklist' if has_dowels else 'not modeled in supplied geometry'),
                     'lookup_factor': config['factors']['service_info'],
                     'procedure_state_only': True},
        'attachment_obligations': copy.deepcopy(attachments),
    }
    if amendment:
        result['checkpoint_revision'] = AMENDMENT_REVISION
        result['amendment_assessments'] = {'loosening':copy.deepcopy(loosened),
                                         'cover_gasket':copy.deepcopy(cover_assessment)}
    if variant_mode and config.get('benchmark_removal'):
        from .checkpoints import evaluate
        result['primary_score'] = evaluate(config, initial_state, rows, final_state, result, attachments)
    return result
