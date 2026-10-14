"""Pending Amendment 1 value scenarios; no runtime imports or action runs.

ASSESS_SCENARIO is an owned future fixture adapter, not a claimed production API.
It must call the amendment scorer with authored/offline values and return its
report. Until the parent publishes that API, every dependent test names its skip.
"""
import copy
import unittest

DIAGRAM_ORDER = (10, 9, 8, 7, 6, 3, 4, 5, 2, 1)
REVERSE_ORDER = tuple(range(10, 0, -1))
PASS_COUNT = 3
ASSESS_SCENARIO = None  # Full scorer adapter; never substitute helper booleans.
LOOSENING_ASSESSMENT = None
COVER_GASKET_ASSESSMENT = None
PURE_PENDING_REASON = 'Amendment 1 pure helper callable not configured; no full scorer credit'
PENDING_REASON = 'Amendment 1 scorer/fixture adapter pending; no current-epoch test or qualification claim'


def row(seq, name, inputs, *, ok=True, observation=None):
    result = {} if observation is None else {'observation': copy.deepcopy(observation)}
    return {'seq': seq, 'name': name, 'input': copy.deepcopy(inputs),
            'ok': ok, 'result': result}


def resequence(rows):
    result = copy.deepcopy(rows)
    for seq, event in enumerate(result, 1):
        event['seq'] = seq
    return result


def loosening_scenarios():
    """Thirty -120-degree operations, with three uniform authored passes."""
    def scenario(name, orders, expected):
        events = [row(0, 'torque', {'part_id': 'hb' + str(position).zfill(2),
                                  'mode': 'loosen', 'angle_deg': -120})
                  for order in orders for position in order]
        events.append(row(0, 'remove', {'part_id': 'head'}))
        return {'name': name, 'kind': 'loosening',
                'fixture_kind': 'authored offline value scenario, not an executed run',
                'service_positions': ['hb' + str(p).zfill(2) for p in range(1, 11)],
                'expected_passes': PASS_COUNT, 'expected_angle_deg': -120,
                'rows': resequence(events), 'expected_CP04': expected,
                'expected_mistake': not expected}
    cases = {
        'diagram_complete': scenario('diagram_complete', [DIAGRAM_ORDER] * PASS_COUNT, True),
        'reverse_complete': scenario('reverse_complete', [REVERSE_ORDER] * PASS_COUNT, True),
        'mixed_between_passes': scenario('mixed_between_passes',
                                        [DIAGRAM_ORDER, REVERSE_ORDER, DIAGRAM_ORDER], False),
        'mixed_within_common_prefix': scenario('mixed_within_common_prefix',
                                              [(10,9,8,7,6,3,5,4,2,1)] * PASS_COUNT, False),
        'missing_member': scenario('missing_member', [DIAGRAM_ORDER[:-1]] * PASS_COUNT, False),
        'duplicate_member': scenario('duplicate_member',
                                    [DIAGRAM_ORDER[:-1] + (2,)] * PASS_COUNT, False),
        'incomplete_last_pass': scenario('incomplete_last_pass',
                                        [DIAGRAM_ORDER, DIAGRAM_ORDER, DIAGRAM_ORDER[:5]], False),
    }
    for name, field, value in (
            ('wrong_angle', 'angle_deg', -90),
            ('boolean_angle', 'angle_deg', False),
            ('positive_angle', 'angle_deg', 120)):
        damaged = copy.deepcopy(cases['diagram_complete'])
        damaged['name'] = name; damaged['expected_CP04'] = False
        damaged['expected_mistake'] = True
        damaged['rows'][5]['input'][field] = value
        cases[name] = damaged
    failed = copy.deepcopy(cases['diagram_complete'])
    failed.update(name='failed_action_does_not_fill_pass', expected_CP04=False, expected_mistake=True)
    failed['rows'][5]['ok'] = False
    cases[failed['name']] = failed
    early = copy.deepcopy(cases['diagram_complete'])
    early.update(name='head_removed_before_complete', expected_CP04=False, expected_mistake=True)
    events = early['rows'][:-1]
    early['rows'] = resequence(events[:25] + [early['rows'][-1]] + events[25:])
    cases[early['name']] = early
    intervening = copy.deepcopy(cases['diagram_complete'])
    intervening['name'] = 'unrelated_look_between_operations'
    intervening['rows'] = resequence(intervening['rows'][:7] + [row(0, 'look', {})] + intervening['rows'][7:])
    cases[intervening['name']] = intervening
    corrected = copy.deepcopy(cases['diagram_complete'])
    corrected.update(name='mixed_prefix_then_corrected', expected_CP04=False, expected_mistake=True)
    bad_pass = copy.deepcopy(cases['mixed_within_common_prefix']['rows'][:10])
    corrected['rows'] = resequence(bad_pass + corrected['rows'])
    cases[corrected['name']] = corrected
    return cases


def cover_scenarios():
    """Detached cover seal identities, current-cycle evidence and new head."""
    def base(name, reuse):
        events = [
            row(0, 'remove', {'part_id': 'gasket_old'}),
            row(0, 'replace', {'part_id': 'gasket_old', 'replacement_id': 'gasket_new'}),
            row(0, 'install', {'part_id': 'gasket_new'}),
            row(0, 'remove', {'part_id': 'cover'}),
            row(0, 'remove', {'part_id': 'cover_gasket_old'}),
            row(0, 'inspect', {'target': 'cover_gasket_old'}, observation={'damaged': False}),
            row(0, 'clean', {'target': 'cover_face', 'method': 'plastic_scraper',
                             'protect_openings': True, 'oil': True, 'sealant': 'cam_holder_corners'}),
        ]
        if not reuse:
            events.append(row(0, 'replace', {'part_id': 'cover_gasket_old',
                                            'replacement_id': 'cover_gasket_new'}))
        active = 'cover_gasket_old' if reuse else 'cover_gasket_new'
        events.extend([row(0, 'install', {'part_id': active}),
                       row(0, 'install', {'part_id': 'cover'}), row(0, 'finish', {})])
        return {'name': name, 'kind': 'cover',
                'fixture_kind': 'authored offline value scenario, not an executed run',
                'rows': resequence(events), 'active_cover_id': active,
                'active_head_gasket_id': 'gasket_new', 'expected_CP12': True,
                'expected_CP08': True, 'expected_cover_accuracy': True,
                'expected_mistake': False,
                'final_cover_flags': {'tube_seals_oiled': True, 'cam_holder_corner_sealant': True},
                'attachment_restoration': 'all declared obligations satisfied by independent adapter'}
    cases = {'cover_new': base('cover_new', False), 'cover_original_reuse': base('cover_original_reuse', True)}
    for name, modify in (
            ('missing_current_inspection', lambda events: [r for r in events if r['name'] != 'inspect']),
            ('missing_sealant', lambda events: _change_input(events, 'clean', 'sealant', None)),
            ('wrong_sealant_site', lambda events: _change_input(events, 'clean', 'sealant', 'whole_surface')),
            ('missing_oil', lambda events: _change_input(events, 'clean', 'oil', False)),
            ('inspection_of_other_identity', lambda events: _change_input(events, 'inspect', 'target', 'gasket_old'))):
        damaged = copy.deepcopy(cases['cover_original_reuse'])
        damaged.update(name=name, expected_CP12=False, expected_cover_accuracy=False, expected_mistake=True)
        damaged['rows'] = resequence(modify(damaged['rows']))
        cases[name] = damaged
    for name, value, ok in (('damaged_original', True, True),
                            ('nonboolean_inspection_condition', 0, True),
                            ('failed_inspection', False, False)):
        damaged = copy.deepcopy(cases['cover_original_reuse'])
        damaged.update(name=name, expected_CP12=False, expected_cover_accuracy=False, expected_mistake=True)
        inspection = next(r for r in damaged['rows'] if r['name'] == 'inspect')
        inspection['result']['observation']['damaged'] = value
        inspection['ok'] = ok
        cases[name] = damaged
    stale = copy.deepcopy(cases['cover_original_reuse'])
    stale.update(name='stale_previous_cycle_inspection_and_treatment', expected_CP12=False,
                 expected_cover_accuracy=False, expected_mistake=True)
    split = next(i for i, r in enumerate(stale['rows']) if r['name'] == 'install'
                 and r['input']['part_id'] == 'cover_gasket_old')
    events = stale['rows'][:split + 2] + [
        row(0, 'remove', {'part_id': 'cover'}), row(0, 'remove', {'part_id': 'cover_gasket_old'}),
        row(0, 'install', {'part_id': 'cover_gasket_old'}), row(0, 'install', {'part_id': 'cover'}),
        row(0, 'finish', {})]
    stale['rows'] = resequence(events)
    cases[stale['name']] = stale
    head = copy.deepcopy(cases['cover_original_reuse'])
    head.update(name='original_head_gasket_forbidden', active_head_gasket_id='gasket_old',
                expected_CP08=False, expected_CP12=False, expected_mistake=True)
    head['rows'] = resequence([r for r in head['rows'] if not (r['name']=='replace'
        and r['input'].get('part_id')=='gasket_old')])
    for event in head['rows']:
        if event['name']=='install' and event['input'].get('part_id')=='gasket_new':
            event['input']['part_id']='gasket_old'
    cases[head['name']] = head
    return cases


def _change_input(events, name, field, value):
    events = copy.deepcopy(events)
    next(r for r in events if r['name'] == name)['input'][field] = value
    return events



def loosen_inputs(name):
    scenario = loosening_scenarios()[name]
    ids = ['hb' + str(index).zfill(2) for index in range(1, 11)]
    config = {'geometry': {
        'parts': [{'id': 'head', 'role': 'head'}] + [
            {'id': ident, 'role': 'head_bolt'} for ident in ids],
        'fasteners': [{'id': ident, 'group': 'head', 'sequence_index': index,
                       'service_required': True, 'initial_engagement_turns': 1}
                      for index, ident in enumerate(ids, 1)]},
        'repair_scoring': {'reference': {'actions': [
            {key: copy.deepcopy(event[key]) for key in ('seq', 'name', 'input')}
            for event in loosening_scenarios()['reverse_complete']['rows']]}},
        'policy': {}}
    initial = {'parts': {ident: {'location': 'assembly', 'damaged': False}
                         for ident in ['head', *ids]},
               'bolts': {ident: {'turns': 1} for ident in ids}}
    return {'config': config, 'initial': initial, 'rows': copy.deepcopy(scenario['rows'])}


def cover_inputs(name):
    scenario = cover_scenarios()[name]
    roles = {'cover': 'valve_cover', 'head': 'head',
             'cover_gasket_old': 'cover_gasket_old', 'cover_gasket_new': 'cover_gasket_new',
             'gasket_old': 'gasket_old', 'gasket_new': 'gasket_new'}
    active = scenario['active_cover_id']; head = scenario['active_head_gasket_id']
    locations = {'cover': 'assembly', 'head': 'assembly',
                 'cover_gasket_old': 'assembly' if active == 'cover_gasket_old' else 'waste',
                 'cover_gasket_new': 'assembly' if active == 'cover_gasket_new' else 'supply',
                 'gasket_old': 'assembly' if head == 'gasket_old' else 'waste',
                 'gasket_new': 'assembly' if head == 'gasket_new' else 'supply'}
    config = {'geometry': {'parts': [{'id': ident, 'role': role} for ident, role in roles.items()],
                           'fasteners': []},
              'benchmark_removal': {'source_to_body': {'valve_cover_gasket_old': 'cover_gasket_old'},
                'reassembly': {'requirements': [
                    {'original_id': 'valve_cover_gasket_old', 'original_may_be_reinstalled': False},
                    {'original_id': 'gasket_old', 'original_may_be_reinstalled': False}]}},
              'policy': {}}
    final = {'parts': {ident: {'location': location, 'damaged': False}
                       for ident, location in locations.items()},
             'gasket': {'active_id': head},
             'surfaces': {'cover_face': {**copy.deepcopy(scenario['final_cover_flags']),
                 'residue_fraction': 0, 'dry': True, 'damaged': False, 'debris_count': 0}}, 
             'benchmark_removal': {'replacements': {} if active == 'cover_gasket_old'
                                   else {'valve_cover_gasket_old': active}}}
    if name == 'damaged_original':
        final['parts']['cover_gasket_old']['damaged'] = True
    return {'config': config, 'rows': copy.deepcopy(scenario['rows']), 'final': final}


def carried_reuse_inputs():
    values = cover_inputs('cover_original_reuse')
    events = values['rows']
    events = [event for event in events
              if not (event['name'] in ('remove', 'install')
                      and event['input'].get('part_id') == 'cover_gasket_old')]
    for event in events:
        if event['name'] in ('remove', 'install') and event['input'].get('part_id') == 'cover':
            event['result']['carried_body_ids'] = ['cover_gasket_old']
    values['rows'] = resequence(events)
    return values


class Amendment1HelperControls(unittest.TestCase):
    """Direct helper values only: no synthetic full-score wrapper."""
    def loosen(self, values):
        if LOOSENING_ASSESSMENT is None:
            self.skipTest(PURE_PENDING_REASON)
        values = copy.deepcopy(values)
        return LOOSENING_ASSESSMENT(values['config'], values['initial'], values['rows'])

    def cover(self, values):
        if COVER_GASKET_ASSESSMENT is None:
            self.skipTest(PURE_PENDING_REASON)
        values = copy.deepcopy(values)
        return COVER_GASKET_ASSESSMENT(values['config'], values['rows'], values['final'])

    def test_loosen_complete_orders(self):
        for name, expected in (('diagram_complete', DIAGRAM_ORDER),
                               ('reverse_complete', REVERSE_ORDER),
                               ('unrelated_look_between_operations', DIAGRAM_ORDER)):
            with self.subTest(name=name):
                values = loosen_inputs(name); assessment = self.loosen(values)
                for field in ('passed', 'order_valid', 'increments_valid', 'disengaged'):
                    self.assertIs(assessment[field], True)
                self.assertEqual(assessment['accepted_order'], list(expected))
                self.assertEqual(assessment['violation_sequences'], [])
                self.assertEqual(assessment['observed_sequences'], [
                    event['seq'] for event in values['rows'] if event['name']=='torque'])

    def test_loosen_mixed_or_malformed(self):
        for name, scenario in loosening_scenarios().items():
            if scenario['expected_CP04']:
                continue
            with self.subTest(name=name):
                self.assertIs(self.loosen(loosen_inputs(name))['passed'], False)

    def test_loosen_census_rejects_duplicate_body_identity(self):
        values = loosen_inputs('reverse_complete')
        values['config']['geometry']['fasteners'][8]['id'] = 'hb10'
        for events in (values['rows'], values['config']['repair_scoring']['reference']['actions']):
            for event in events:
                if event['input'].get('part_id') == 'hb09':
                    event['input']['part_id'] = 'hb10'
        self.assertIs(self.loosen(values)['passed'], False)

    def test_loosen_reference_increment_is_typed(self):
        values = loosen_inputs('reverse_complete')
        values['config']['repair_scoring']['reference']['actions'][5]['input']['angle_deg'] = False
        self.assertIs(self.loosen(values)['reference_valid'], False)

    def test_loosen_wrong_increment_can_disengage_without_credit(self):
        values = loosen_inputs('reverse_complete')
        for event in values['rows']:
            if event['name']=='torque':
                event['input']['angle_deg'] = -180
        assessment = self.loosen(values)
        self.assertIs(assessment['disengaged'], True)
        self.assertIs(assessment['increments_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_loosen_order_violation_retains_failure_after_completion(self):
        assessment = self.loosen(loosen_inputs('mixed_between_passes'))
        self.assertIs(assessment['disengaged'], True)
        self.assertIs(assessment['increments_valid'], True)
        self.assertIs(assessment['order_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_loosen_initial_engagement_must_be_fully_released(self):
        values = loosen_inputs('reverse_complete')
        values['initial']['bolts']['hb01']['turns'] = 1.5
        assessment = self.loosen(values)
        self.assertIs(assessment['disengaged'], False)
        self.assertIs(assessment['passed'], False)

    def test_loosen_successful_head_removal_is_required(self):
        values = loosen_inputs('reverse_complete')
        values['rows'][-1]['ok'] = False
        self.assertIs(self.loosen(values)['passed'], False)

    def test_cover_new_and_detached_original(self):
        for name, route in (('cover_new', 'new'), ('cover_original_reuse', 'original_reuse')):
            with self.subTest(name=name):
                assessment = self.cover(cover_inputs(name))
                for field in ('passed', 'source_binding_valid', 'treatment_valid', 'refit_valid'):
                    self.assertIs(assessment[field], True)
                self.assertEqual(assessment['route'], route)
                self.assertEqual(assessment['current_cycle_start'], 5)

    def test_cover_incomplete_reuse_evidence(self):
        for name, scenario in cover_scenarios().items():
            if scenario['expected_cover_accuracy']:
                continue
            with self.subTest(name=name):
                self.assertIs(self.cover(cover_inputs(name))['passed'], False)

    def test_cover_fresh_cycle_restores_helper_credit(self):
        values = cover_inputs('stale_previous_cycle_inspection_and_treatment')
        boundary = max(index for index, event in enumerate(values['rows'])
                       if event['name']=='remove' and event['input'].get('part_id')=='cover_gasket_old')
        values['rows'] = resequence(values['rows'][:boundary+1] + [
            row(0, 'inspect', {'target': 'cover_gasket_old'}, observation={'damaged': False}),
            row(0, 'clean', {'target': 'cover_face', 'method': 'plastic_scraper',
                             'protect_openings': True, 'oil': True, 'sealant': 'cam_holder_corners'}),
        ] + values['rows'][boundary+1:])
        self.assertIs(self.cover(values)['passed'], True)

    def test_cover_carried_original_reuse(self):
        assessment = self.cover(carried_reuse_inputs())
        self.assertIs(assessment['passed'], True)
        self.assertEqual(assessment['route'], 'original_reuse')
        self.assertEqual(assessment['current_cycle_start'], 4)

    def test_cover_carried_refit_needs_exact_member_list(self):
        for witness in ('prefix-cover_gasket_old-suffix', None, 0,
                        ['cover_gasket_old', 'cover_gasket_old'], ['cover_gasket_old', 1]):
            with self.subTest(witness=witness):
                values = carried_reuse_inputs()
                for event in values['rows']:
                    if event['name']=='install' and event['input'].get('part_id')=='cover':
                        event['result']['carried_body_ids'] = witness
                self.assertIs(self.cover(values)['passed'], False)

    def test_cover_carried_type_guard_is_not_masked_by_duplicates(self):
        values = carried_reuse_inputs()
        for part in values['config']['geometry']['parts']:
            if part['id']=='cover_gasket_old':
                part['id']='x'
        values['config']['benchmark_removal']['source_to_body']['valve_cover_gasket_old']='x'
        values['final']['parts']['x']=values['final']['parts'].pop('cover_gasket_old')
        for event in values['rows']:
            if event['input'].get('target')=='cover_gasket_old':
                event['input']['target']='x'
            if 'carried_body_ids' in event['result']:
                event['result']['carried_body_ids']=['x']
        self.assertIs(self.cover(values)['passed'], True)
        for event in values['rows']:
            if event['name']=='install' and event['input'].get('part_id')=='cover':
                event['result']['carried_body_ids']='x'
        self.assertIs(self.cover(values)['passed'], False)

    def test_cover_carried_refit_cannot_be_missing(self):
        values = carried_reuse_inputs()
        for event in values['rows']:
            if event['name']=='install' and event['input'].get('part_id')=='cover':
                event['result']['carried_body_ids'] = []
        self.assertIs(self.cover(values)['passed'], False)

    def test_cover_source_binding_cannot_be_forged(self):
        for field in ('config_origin', 'final_position'):
            with self.subTest(field=field):
                values = carried_reuse_inputs()
                if field == 'config_origin':
                    values['config']['benchmark_removal']['source_to_body']['valve_cover_gasket_old'] = 'gasket_old'
                else:
                    values['final']['benchmark_removal']['replacements']['valve_cover_gasket_old'] = 'cover_gasket_new'
                self.assertIs(self.cover(values)['source_binding_valid'], False)
                self.assertIs(self.cover(values)['passed'], False)

    def test_cover_treatment_requires_protected_openings(self):
        values = carried_reuse_inputs()
        next(event for event in values['rows'] if event['name']=='clean')['input']['protect_openings'] = False
        assessment = self.cover(values)
        self.assertIs(assessment['treatment_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_cover_treatment_requires_serviceable_surface(self):
        for field, value in (('residue_fraction', 0.1), ('residue_fraction', False),
                             ('residue_fraction', float('inf')), ('dry', False), ('dry', 1),
                             ('damaged', True), ('damaged', 0),
                             ('debris_count', 1), ('debris_count', False), ('debris_count', 0.0),
                             ('tube_seals_oiled', 1), ('cam_holder_corner_sealant', 1)):
            with self.subTest(field=field, value=repr(value)):
                values = carried_reuse_inputs()
                values['final']['surfaces']['cover_face'][field] = value
                assessment = self.cover(values)
                self.assertIs(assessment['treatment_valid'], False)
                self.assertIs(assessment['passed'], False)

    def test_cover_latest_clean_must_retain_current_treatment(self):
        for location in ('before_refit', 'after_refit'):
            with self.subTest(location=location):
                values = carried_reuse_inputs()
                events = values['rows']
                where = next(index for index, event in enumerate(events)
                             if event['name']=='install' and event['input'].get('part_id')=='cover')
                if location == 'after_refit':
                    where += 1
                events.insert(where, row(0, 'clean', {'target': 'cover_face',
                    'method': 'plastic_scraper', 'protect_openings': True,
                    'oil': False, 'sealant': None}))
                values['rows'] = resequence(events)
                assessment = self.cover(values)
                self.assertIs(assessment['treatment_valid'], False)
                self.assertIs(assessment['passed'], False)

    def test_cover_carried_removal_needs_exact_member_list(self):
        for witness in ('prefix-cover_gasket_old-suffix', None, 0,
                        ['cover_gasket_old', 'cover_gasket_old'], ['cover_gasket_old', 1]):
            with self.subTest(witness=witness):
                values = carried_reuse_inputs()
                for event in values['rows']:
                    if event['name']=='remove' and event['input'].get('part_id')=='cover':
                        event['result']['carried_body_ids'] = witness
                self.assertIs(self.cover(values)['passed'], False)

    def test_cover_stale_carried_cycle_does_not_reuse_prior_evidence(self):
        values = carried_reuse_inputs()
        events = values['rows'][:-1] + [
            row(0, 'remove', {'part_id': 'cover'}),
            row(0, 'install', {'part_id': 'cover'}), row(0, 'finish', {})]
        for event in events[-3:-1]:
            event['result']['carried_body_ids'] = ['cover_gasket_old']
        values['rows'] = resequence(events)
        assessment = self.cover(values)
        self.assertIs(assessment['inspection_valid'], False)
        self.assertIs(assessment['treatment_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_cover_new_route_needs_exchange_and_waste(self):
        for omission in ('exchange', 'waste'):
            with self.subTest(omission=omission):
                values = cover_inputs('cover_new')
                if omission == 'exchange':
                    values['rows'] = [event for event in values['rows']
                        if not (event['name']=='replace' and
                                event['input'].get('part_id')=='cover_gasket_old')]
                else:
                    values['final']['parts']['cover_gasket_old']['location'] = 'tray'
                assessment = self.cover(values)
                self.assertIs(assessment['new_replacement_valid'], False)
                self.assertIs(assessment['passed'], False)

    def test_cover_current_last_inspection_is_authoritative(self):
        values = carried_reuse_inputs()
        events = values['rows']
        where = next(index for index, event in enumerate(events) if event['name']=='clean')
        events.insert(where, row(0, 'inspect', {'target': 'cover_gasket_old'}, observation={'damaged': True}))
        values['rows'] = resequence(events)
        assessment = self.cover(values)
        self.assertIs(assessment['inspection_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_cover_refit_needs_undamaged_active_body(self):
        values = cover_inputs('cover_new')
        values['final']['parts']['cover_gasket_new']['damaged'] = True
        assessment = self.cover(values)
        self.assertIs(assessment['refit_valid'], False)
        self.assertIs(assessment['passed'], False)

    def test_cover_original_head_does_not_affect_cover_helper(self):
        self.assertIs(self.cover(cover_inputs('original_head_gasket_forbidden'))['passed'], True)
        # Full primary+secondary integration below must independently fail CP08/CP12.


class Amendment1Controls(unittest.TestCase):
    def assess(self, scenario):
        if ASSESS_SCENARIO is None:
            self.skipTest(PENDING_REASON)
        return ASSESS_SCENARIO(copy.deepcopy(scenario))

    def checkpoint(self, report, ident):
        return next(r for r in report['primary_score']['checkpoints'] if r['id'] == ident)

    def test_two_complete_orders_pass_without_wrong_order(self):
        for name in ('diagram_complete', 'reverse_complete', 'unrelated_look_between_operations'):
            with self.subTest(name=name):
                report = self.assess(loosening_scenarios()[name])
                self.assertIs(self.checkpoint(report, 'CP04')['passed'], True)
                self.assertEqual(report['mistakes']['by_type'].get('wrong_order', 0), 0)

    def test_malformed_or_mixed_orders_fail_with_mistakes(self):
        for name, case in loosening_scenarios().items():
            if case['expected_CP04']:
                continue
            with self.subTest(name=name):
                report = self.assess(case)
                self.assertIs(self.checkpoint(report, 'CP04')['passed'], False)
                self.assertGreater(report['mistakes']['count'], 0)

    def test_same_action_counts_have_same_base_time(self):
        cases = loosening_scenarios()
        reports = [self.assess(cases[n]) for n in
                   ('diagram_complete', 'reverse_complete', 'mixed_between_passes')]
        totals = [sum(r['base_seconds'] for r in report['human_time']['ledger']) for report in reports]
        self.assertEqual(totals[0], totals[1])
        self.assertEqual(totals[0], totals[2])

    def test_cover_new_and_current_original_reuse_pass(self):
        for name in ('cover_new', 'cover_original_reuse'):
            with self.subTest(name=name):
                report = self.assess(cover_scenarios()[name])
                self.assertIs(self.checkpoint(report, 'CP12')['passed'], True)
                self.assertEqual(report['checklist_accuracy']['accuracy_percent'], 100)
                self.assertEqual(report['mistakes']['count'], 0)

    def test_incomplete_reuse_evidence_fails_primary_secondary_and_mistakes(self):
        for name, case in cover_scenarios().items():
            if case['expected_CP12']:
                continue
            with self.subTest(name=name):
                report = self.assess(case)
                self.assertIs(self.checkpoint(report, 'CP12')['passed'], False)
                self.assertLess(report['checklist_accuracy']['accuracy_percent'], 100)
                self.assertGreater(report['mistakes']['count'], 0)

    def test_original_head_remains_forbidden_with_valid_cover_reuse(self):
        report = self.assess(cover_scenarios()['original_head_gasket_forbidden'])
        self.assertIs(self.checkpoint(report, 'CP08')['passed'], False)
        self.assertIs(self.checkpoint(report, 'CP12')['passed'], False)


if __name__ == '__main__':
    unittest.main()
