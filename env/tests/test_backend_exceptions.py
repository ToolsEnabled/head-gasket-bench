"""Bounded pure mocks: every ordinary trusted failure is an atomic attempt."""
import copy
import unittest
from hgj.codec import canonical
from hgj.fixtures import fixture_config, FixtureJoint
from hgj.game import Game, replay


class BackendExceptionTests(unittest.TestCase):
    def test_ordinary_backend_exceptions_rollback_consume_turn_and_replay(self):
        for exception in (ZeroDivisionError, AttributeError):
            with self.subTest(exception=exception.__name__):
                class Broken(FixtureJoint):
                    def apply(self, state, operation):
                        raise exception('private backend detail')
                config = fixture_config()
                config['factors'].update(turn_budget=1, turn_budget_unit='job-tool-action-attempts')
                game = Game(config, joint=Broken())
                before = copy.deepcopy(game.state)
                fasteners = copy.deepcopy(game.fasteners)
                result = game.call('torque', {'part_id': 'cb01', 'mode': 'loosen', 'angle_deg': -120})
                self.assertEqual(result, {'ok': False, 'refusal': 'Trusted computation unavailable',
                                         'backend_error': exception.__name__, 'turns_remaining': 0})
                self.assertEqual(game.state, before)
                self.assertEqual(game.fasteners, fasteners)
                self.assertEqual(len(game.records), 1)
                self.assertTrue(game.budget()['exhausted'])
                self.assertEqual(canonical(replay(game.export(), joint=Broken())), canonical(game.export()))

    def test_finish_backend_exception_keeps_job_open_and_endpoint_unchanged(self):
        class BrokenSoak:
            def score(self, state):
                raise ArithmeticError('private scorer detail')
        game = Game(fixture_config(), joint=FixtureJoint(), soak=BrokenSoak())
        before = copy.deepcopy(game.state)
        result = game.call('finish', {})
        self.assertFalse(result['ok'])
        self.assertEqual(result['backend_error'], 'ArithmeticError')
        self.assertEqual(game.state, before)
        self.assertIsNone(game.score)
        self.assertFalse(game.finished)
        self.assertEqual(len(game.records), 1)
        self.assertEqual(canonical(replay(game.export(), joint=FixtureJoint(), soak=BrokenSoak())), canonical(game.export()))
