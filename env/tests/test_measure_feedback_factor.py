"""Feedback changes observations, not instrument preconditions or job clock."""
import copy
import unittest
from hgj.game import Game
from tests import test_bolt_length_transport as transport

class MeasureFeedbackFactorTests(unittest.TestCase):
    def game(self,feedback,withdraw=False):
        c=transport.BoltLengthTransportTests().config(61.8);c['factors']['feedback']=feedback
        c['factors']['turn_budget_unit']='job-tool-action-attempts';game=Game(c)
        self.assertTrue(game.call('remove',{'part_id':'belt'})['ok'])
        if withdraw:
            self.assertTrue(game.call('torque',{'part_id':'hb03','mode':'loosen','angle_deg':-360})['ok'])
            self.assertTrue(game.call('remove',{'part_id':'hb03'})['ok'])
        return game

    def test_instrument_refusals_and_attempt_accounting_are_identical_when_feedback_is_off(self):
        for feedback in (True,False):
            for kind,withdraw in (('bolt_stretch',False),('bolt_free_length',False),('roughness',True)):
                with self.subTest(feedback=feedback,kind=kind):
                    game=self.game(feedback,withdraw);before=copy.deepcopy(game.state)
                    used=game.budget()['attempted_calls'];result=game.call('measure',{'target':'hb03','kind':kind})
                    self.assertFalse(result['ok']);self.assertEqual(game.state,before)
                    self.assertEqual(game.budget()['attempted_calls'],used+1)

    def test_valid_caliper_actions_keep_clock_and_history_while_only_value_feedback_changes(self):
        games=[self.game(feedback,True) for feedback in (True,False)];results=[]
        for game in games:
            result=game.call('measure',{'target':'hb03','kind':'bolt_free_length'});self.assertTrue(result['ok'],result);results.append(result)
        self.assertEqual(results[0]['observation']['value'],61.8)
        self.assertEqual(results[1]['observation'],{'feedback':'disabled'})
        self.assertEqual(games[0].state['action_history'],games[1].state['action_history'])
        self.assertEqual(games[0].state['revision'],games[1].state['revision'])
        self.assertEqual(games[0].state['simulated_labor_s'],games[1].state['simulated_labor_s'])
