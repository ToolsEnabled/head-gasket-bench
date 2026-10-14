"""Malformed source-number controls, not selected length/material estimates."""
import copy
import unittest
from hgj.game import Game
from hgj.codec import digest
from hgj.action_conditions import apply_effects
from tests import test_bolt_length_transport as transport

class BoltLengthNumericRefusalTests(unittest.TestCase):
    def test_initial_extreme_integer_is_a_value_refusal(self):
        config=transport.BoltLengthTransportTests().config(10**400)
        with self.assertRaises(ValueError):Game(config)

    def test_effect_extreme_integer_is_an_atomic_value_refusal(self):
        before={'parts':{},'bolts':{'b':{'free_length_mm':61.5}},'surfaces':{},'gasket':{},'timing':{}}
        prior=copy.deepcopy(before);op={'before_conditions':before,'before_conditions_sha256':digest(before)}
        packet={'schema':'hgj/action-conditions/v1','operation_sha256':digest(op),
            'before_conditions_sha256':digest(before),'fields':{'/bolts/b/free_length_mm':{'value':10**400,
                'source_sha256':'a'*64,'status':'estimated','note':'Invalid oversized integer; no hardware datum'}}}
        with self.assertRaises(ValueError):apply_effects(before,op,packet,
            required_paths={'/bolts/b/free_length_mm'},allowed_paths={'/bolts/b/free_length_mm'},source_pins={'a'*64})
        self.assertEqual(before,prior)
