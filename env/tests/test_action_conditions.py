"""Tiny source-effect transport tests; no physical model or admission."""
import copy
import unittest
from hgj.codec import canonical, digest


class ActionConditionsTests(unittest.TestCase):
    def fixture(self):
        before = {'parts': {'bolt/μ': {'location': 'tray', 'damaged': False}},
                  'bolts': {'bolt/μ': {'stretch_mm': 0.03, 'thread_clean': False,
                                     'turns': 0, 'history': []}},
                  'surfaces': {'head_face': {'residue_fraction': 1, 'dry': False,
                                'debris_count': 0, 'warpage_m': None}},
                  'gasket': {'active_id': None, 'orientation': 'up'},
                  'timing': {'cam_phase_deg': 0, 'crank_phase_deg': 0, 'checks': []}}
        operation = {'kind': 'clean', 'target': 'bolt/μ', 'method': 'thread_brush',
                     'before_conditions': copy.deepcopy(before),
                     'before_conditions_sha256': digest(before)}
        path = '/bolts/bolt~1μ/thread_clean'
        packet = {'schema': 'hgj/action-conditions/v1',
                  'operation_sha256': digest(operation),
                  'before_conditions_sha256': digest(before),
                  'fields': {path: {'value': True, 'status': 'estimated',
                                   'source_sha256': 'a' * 64,
                                   'note': 'Synthetic transport fixture only'}}}
        return before, operation, packet, path

    def apply(self, before, operation, packet, required):
        from hgj.action_conditions import apply_effects
        return apply_effects(before, operation, packet,
                             required_paths=required, allowed_paths=required,
                             source_pins={'a' * 64})

    def test_exact_pointer_valid_effect_and_explicit_unknown_are_lossless(self):
        before, operation, packet, path = self.fixture()
        original = canonical(before)
        result = self.apply(before, operation, packet, {path})
        self.assertTrue(result['bolts']['bolt/μ']['thread_clean'])
        self.assertEqual(canonical(before), original)
        unknown = '/surfaces/head_face/warpage_m'
        packet['fields'] = {unknown: {'value': None, 'status': 'unknown',
            'source_sha256': 'a' * 64, 'note': 'Residual warpage is unsupported'}}
        result = self.apply(before, operation, packet, {unknown})
        self.assertIsNone(result['surfaces']['head_face']['warpage_m'])
        self.assertEqual(canonical(result), canonical(self.apply(before, operation, packet, {unknown})))

    def test_corrupt_or_unbound_effects_refuse_without_mutating_input(self):
        for kind in ('operation', 'before', 'command_before', 'missing', 'location',
                     'invented_field', 'unknown_body', 'source', 'null_status',
                     'numeric_bool', 'nonfinite', 'residue_range', 'pointer_alias'):
            before, operation, packet, path = self.fixture()
            required = {path}
            if kind == 'operation': packet['operation_sha256'] = 'b' * 64
            elif kind == 'before': packet['before_conditions_sha256'] = 'b' * 64
            elif kind == 'command_before': operation['before_conditions']['bolts']['bolt/μ']['stretch_mm'] = 0
            elif kind == 'missing': packet['fields'] = {}
            elif kind in ('location', 'invented_field', 'unknown_body', 'pointer_alias'):
                bad = {'location': '/parts/bolt~1μ/location', 'invented_field': '/surfaces/head_face/pressure',
                       'unknown_body': '/bolts/absent/thread_clean',
                       'pointer_alias': '/bolts/bolt~01μ/thread_clean'}[kind]
                packet['fields'] = {bad: next(iter(packet['fields'].values()))}; required = {bad}
            elif kind == 'source': packet['fields'][path]['source_sha256'] = 'b' * 64
            elif kind == 'null_status': packet['fields'][path]['value'] = None
            else:
                bad = '/bolts/bolt~1μ/stretch_mm' if kind in ('numeric_bool', 'nonfinite') else '/surfaces/head_face/residue_fraction'
                value = True if kind == 'numeric_bool' else float('nan') if kind == 'nonfinite' else 1.1
                packet['fields'] = {bad: {'value': value, 'status': 'estimated',
                    'source_sha256': 'a' * 64, 'note': 'Invalid synthetic input'}}; required = {bad}
            original = canonical(before)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.apply(before, operation, packet, required)
            self.assertEqual(canonical(before), original)

    def test_absent_supported_domain_refuses_even_well_formed_packet(self):
        before, operation, packet, path = self.fixture()
        for required in (None, set()):
            with self.subTest(required=required), self.assertRaises(ValueError):
                self.apply(before, operation, packet, required)

    def test_late_invalid_field_and_malformed_provenance_are_atomic(self):
        for kind in ('late_invalid', 'source_type', 'empty_note'):
            before, operation, packet, path = self.fixture()
            if kind == 'late_invalid':
                packet['fields']['/surfaces/head_face/debris_count'] = {
                    'value': -1, 'status': 'estimated', 'source_sha256': 'a' * 64,
                    'note': 'Invalid final field after a valid first field'}
            elif kind == 'source_type': packet['fields'][path]['source_sha256'] = []
            else: packet['fields'][path]['note'] = ' '
            original = canonical(before)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.apply(before, operation, packet, {path})
            self.assertEqual(canonical(before), original)

    def test_existing_field_outside_operation_maximum_is_refused(self):
        from hgj.action_conditions import apply_effects
        before, operation, packet, path = self.fixture()
        extra = '/bolts/bolt~1μ/stretch_mm'
        packet['fields'][extra] = {'value': 0, 'status': 'estimated',
            'source_sha256': 'a' * 64, 'note': 'Shared source does not authorize an extra condition'}
        original = canonical(before)
        with self.assertRaisesRegex(ValueError, 'authorized operation domain'):
            apply_effects(before, operation, packet, required_paths={path},
                          allowed_paths={path}, source_pins={'a' * 64})
        self.assertEqual(canonical(before), original)

    def test_required_and_allowed_paths_must_describe_one_explicit_domain(self):
        from hgj.action_conditions import apply_effects
        before, operation, packet, path = self.fixture()
        for maximum in (None, set(), {'/surfaces/head_face/dry'}):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                apply_effects(before, operation, packet, required_paths={path},
                              allowed_paths=maximum, source_pins={'a' * 64})

    def test_an_explicitly_authorized_optional_effect_is_lossless(self):
        from hgj.action_conditions import apply_effects
        before, operation, packet, path = self.fixture()
        extra = '/bolts/bolt~1μ/stretch_mm'
        packet['fields'][extra] = {'value': 0.04, 'status': 'estimated',
            'source_sha256': 'a' * 64, 'note': 'Explicit optional synthetic transport effect'}
        after = apply_effects(before, operation, packet, required_paths={path},
                              allowed_paths={path, extra}, source_pins={'a' * 64})
        self.assertEqual(after['bolts']['bolt/μ']['stretch_mm'], 0.04)
        self.assertEqual(before['bolts']['bolt/μ']['stretch_mm'], 0.03)
