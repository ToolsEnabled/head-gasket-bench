"""Prepare trusted procedure-accuracy configurations and scripted scorer cases.

Mechanical conditions and geometry remain explicit stand-ins until separately
received source inputs replace them. This module executes no engine model.
"""
import copy
import json
from pathlib import Path
from hgj.codec import digest
from hgj.fixtures import fixture_config, correct_job
from hgj.game import Game
from hgj.human_time import policy_from_labor
from hgj.repair_scoring import MODE, build_reference

CONTROLS = ('correct', 'wrong_torque_sequence', 'under_torque', 'skipped_final_stage',
            'wrong_gasket', 'reused_stretched_bolt', 'wrong_timing')
LOOKUPS = {
    'torque': {'query': 'head torque stages', 'entry_ids': ['E04']},
    'sequence': {'query': 'head tightening sequence', 'entry_ids': ['E03']},
    'timing': {'query': 'timing marks', 'entry_ids': ['E10']},
    'bolt_reuse': {'query': 'bolt reuse', 'entry_ids': ['E05', 'E12']},
    'flatness': {'query': 'deck flatness', 'entry_ids': ['E06']},
}


def actions_for(config, name='correct'):
    if name not in CONTROLS:
        raise ValueError('Unknown registered accuracy control')
    original = copy.deepcopy(config)
    original.pop('repair_scoring', None)
    class Collector:
        def __init__(self):
            self.metadata = Game(original)
            self.actions = []
        def __getattr__(self, key):
            return getattr(self.metadata, key)
        def call(self, action, args):
            self.actions.append({'name': action, 'input': copy.deepcopy(args)})
            return {'ok': True}
    collector = Collector()
    old_name = 'skipped_retorque' if name == 'skipped_final_stage' else name
    correct_job(collector, bad=None if name == 'correct' else old_name)
    preamble = [{'name': 'look', 'input': {}},
                {'name': 'inspect', 'input': {'target': collector.public_id(collector.role('gasket_new'))}}]
    preamble += [{'name': 'search_service_info', 'input': {'query': item['query']}}
                 for item in LOOKUPS.values()]
    return preamble + collector.actions


def prepare_config(config, reference_actions=None, human_time_policy=None):
    """The host, not a public tool, defines the reference before any scored run."""
    base = copy.deepcopy(config)
    base.pop('repair_scoring', None)
    # The reference is independent of experimental service/feedback availability.
    reference_config = copy.deepcopy(base)
    reference_config['factors'].update(service_info=True, feedback=True)
    game = Game(reference_config)
    initial = copy.deepcopy(game.state)
    for row in (actions_for(reference_config) if reference_actions is None else reference_actions):
        reply = game.call(row['name'], row['input'])
        if not reply['ok']:
            raise ValueError('Correct reference procedure refused an action')
    reference = build_reference(base, initial, game.records, game.state)
    base['repair_scoring'] = {
        'mode': MODE, 'reference': reference, 'reference_sha256': digest(reference),
        'human_time_policy': policy_from_labor(base['labor']) if human_time_policy is None else copy.deepcopy(human_time_policy),
        'lookup_categories': {**{key: value['entry_ids'] for key, value in LOOKUPS.items()},
                              'gasket': ['E09']},
    }
    return base


def example_config(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    config = fixture_config()
    # The public tree ships the current labor table only (labor-v2.json).
    config['service'] = json.loads((root / 'data' / 'service.json').read_bytes())
    config['labor'] = json.loads((root / 'data' / 'labor-v2.json').read_bytes())
    retained = json.loads((root / 'data' / 'procedure-retained-bodies.json').read_bytes())
    config['geometry']['parts'].extend(copy.deepcopy(retained['parts']))
    config['geometry']['retained_body_source'] = retained
    return prepare_config(config)
