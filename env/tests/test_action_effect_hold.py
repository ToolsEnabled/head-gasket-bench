"""Tiny transport fixtures: physical commands cannot inherit fixture effects."""
import copy
import unittest
from hgj.codec import digest
from hgj.game import Game
from tests.test_initial_conditions import InitialConditionsTests


class ActionEffectHoldTests(unittest.TestCase):
    def config(self):
        config = InitialConditionsTests().config()
        config['admission'] = {'status': 'validated-physics',
                               'initial_conditions_sha256': digest(config['initial_conditions'])}
        config['factors'].update(turn_budget=1, turn_budget_unit='job-tool-action-attempts')
        return config

    def test_physical_commands_refuse_atomically_without_effect_laws(self):
        actions = [('remove', {'part_id': 'belt'}), ('install', {'part_id': 'belt',
                    'cam_phase_deg': 0, 'crank_phase_deg': 0}),
                   ('clean', {'target': 'hb01', 'method': 'thread_brush'}),
                   ('replace', {'part_id': 'hb03', 'replacement_id': 'new_hb03'}),
                   ('torque', {'part_id': 'cb01', 'mode': 'loosen', 'angle_deg': -120}),
                   ('check_timing', {'crank_revolutions': 4})]
        for name, args in actions:
            with self.subTest(action=name):
                game = Game(self.config())
                # These locations only make fixture commands otherwise legal.
                # No source conditions, admitted physics, or actual task created.
                if name == 'install': game.state['parts']['belt']['location'] = 'tray'
                if name == 'clean': game.state['parts']['hb01']['location'] = 'tray'
                if name == 'replace': game.state['parts']['hb03']['location'] = 'tray'
                before = copy.deepcopy(game.state)
                mappings = copy.deepcopy(game.fasteners)
                result = game.call(name, args)
                self.assertEqual(result, {'ok': False,
                    'refusal': 'Source-defined physical action effects are not admitted',
                    'turns_remaining': 0})
                self.assertEqual(game.state, before)
                self.assertEqual(game.fasteners, mappings)
                self.assertEqual(len(game.records), 1)
                self.assertTrue(game.budget()['exhausted'])

    def test_lookup_remains_available_and_hold_replays_exactly(self):
        from hgj.codec import canonical
        from hgj.game import replay
        config = self.config()
        game = Game(config)
        result = game.call('check_timing', {'crank_revolutions': 4})
        self.assertFalse(result['ok'])
        self.assertEqual(canonical(replay(game.export())), canonical(game.export()))
        other = Game(config)
        self.assertTrue(other.call('search_service_info', {'query': 'head bolts'})['ok'])
