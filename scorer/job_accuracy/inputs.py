"""Receive exported repair-start evidence; hashes are not runtime provenance."""
from .independent import check, equal, fingerprint

MECHANICAL_KEYS = ('parts', 'bolts', 'surfaces', 'gasket', 'timing')


def initial_evidence(record, reference):
    present = 'initial_state' in record or 'initial_state_sha256' in record
    if not present:
        return {'available': False, 'reason': 'Repair-start state was not supplied',
                'runtime_source_authenticated': False}
    initial = record.get('initial_state'); config = record['config']; actions = record['actions']
    check(type(initial) is dict and record.get('initial_state_sha256') == fingerprint(initial),
          'initial-state-commitment')
    check(initial['identity']['config_sha256'] == record['config_sha256']
          and record['config_sha256'] == fingerprint(config)
          and initial['variant_id'] == config['variant_id'], 'initial-config-binding')
    check(type(initial.get('revision')) is int and initial['revision'] == 0
          and equal(initial.get('action_history'), [])
          and equal(initial.get('service_receipts', []), [])
          and equal(initial.get('service_replacements', {}), {}), 'initial-empty-history')
    mechanical = {key: initial[key] for key in MECHANICAL_KEYS}
    check(reference['initial_sha256'] == fingerprint(mechanical), 'initial-reference-projection')
    check((actions[0]['pre_state_sha256'] if actions else record['final_state_sha256'])
          == record['initial_state_sha256'], 'initial-journal-join')
    definitions = {p['id']: p for p in config['geometry']['parts']}
    expected = {p: ('assembly' if d['installed'] else 'unavailable'
                    if config.get('benchmark_task') and d.get('available_in_bin') is False else 'supply')
                for p, d in definitions.items()}
    check(set(initial['parts']) == set(definitions)
          and all(initial['parts'][p]['location'] == place for p, place in expected.items()),
          'initial-location-binding')
    spec = config.get('benchmark_removal')
    if spec is not None:
        policy = spec['policy']
        expected_removal = {'policy_sha256': spec['policy_sha256'], 'physical_qualification': False,
                            'released': {key: False for key in policy['release_actions']},
                            'conditions': {key: False for key in policy['condition_ids']},
                            'replacements': {}, 'movements': [], 'attachment_history': []}
        check(equal(initial.get('benchmark_removal'), expected_removal), 'initial-removal-baseline')
    factors = config['factors']; unit = factors.get('turn_budget_unit'); budget = record.get('budget')
    check(unit in (None, 'job-tool-action-attempts') and (budget is None if unit is None else type(budget) is dict),
          'initial-budget-presence')
    if budget is not None:
        limit = factors['turn_budget']; count = len(actions)
        check(type(limit) is int and limit > 0 and type(budget.get('limit')) is int
              and budget['limit'] == limit and budget.get('unit') == unit
              and type(budget.get('used')) is int and budget['used'] == min(count, limit)
              and type(budget.get('attempted_calls')) is int and budget['attempted_calls'] == count
              and type(budget.get('exhausted')) is bool and budget['exhausted'] == (count >= limit),
              'initial-budget-accounting')
    return {'available': True, 'initial_state_sha256': record['initial_state_sha256'],
            'reference_mechanical_sha256': reference['initial_sha256'],
            'first_action_or_empty_final_joined': True, 'parts': len(definitions),
            'budget_checked': budget is not None, 'runtime_source_authenticated': False,
            'scope': 'Exported initial values and commitments joined; source custody is checked separately'}
