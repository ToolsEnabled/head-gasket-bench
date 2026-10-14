"""Thread-start preconditions; synthetic source geometry, no joint model."""
import copy
import unittest
from hgj.game import Game,replay
from tests import test_bolt_length_transport as transport

class TorqueEngagementOrderTests(unittest.TestCase):
    def game(self):
        game=Game(transport.BoltLengthTransportTests().config(61.8))
        self.assertTrue(game.call('remove',{'part_id':'belt'})['ok']);return game

    def test_disengaged_target_or_group_mate_cannot_be_torqued_before_starting_threads(self):
        for disengaged in ('hb03','hb02'):
            with self.subTest(disengaged=disengaged):
                game=self.game()
                self.assertTrue(game.call('torque',{'part_id':disengaged,'mode':'loosen','angle_deg':-360})['ok'])
                before=copy.deepcopy(game.state);attempts=game.budget()['attempted_calls']
                result=game.call('torque',{'part_id':'hb03','mode':'tighten','value_N_m':30})
                self.assertFalse(result['ok']);self.assertEqual(game.state,before)
                self.assertEqual(game.budget()['attempted_calls'],attempts+1)
                self.assertEqual(replay(game.export()),game.export())

    def test_refitting_declared_thread_engagement_restores_valid_tightening(self):
        game=self.game()
        for name,args in [('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360}),
                          ('remove',{'part_id':'hb03'}),('install',{'part_id':'hb03'}),
                          ('torque',{'part_id':'hb03','mode':'tighten','value_N_m':30})]:
            result=game.call(name,args);self.assertTrue(result['ok'],result)
        self.assertEqual(game.state['bolts']['hb03']['turns'],3.5)
        self.assertEqual(replay(game.export()),game.export())
