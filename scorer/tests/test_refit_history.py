"""Historical refits cannot acquire evidence from a later correction."""
from copy import deepcopy
import unittest
from job_accuracy.refits import cover_refits
from job_accuracy.independent import checklist


def row(seq, name, args, **result):
    return {'seq': seq, 'name': name, 'input': args, 'result': {'ok': True, **result}}


def example():
    config = {'variant_id': 'V1', 'policy': {}, 'geometry': {'parts': [
        {'id': 'cover', 'role': 'valve_cover', 'installed': True},
        {'id': 'old', 'role': 'cover_gasket_old', 'installed': True},
        {'id': 'new', 'role': 'cover_gasket_new', 'installed': False}]},
        'benchmark_removal': {'source_to_body': {'valve_cover_gasket_old': 'old'}}}
    initial = {'parts': {'cover': {'location': 'assembly', 'damaged': False},
                        'old': {'location': 'assembly', 'damaged': False},
                        'new': {'location': 'supply', 'damaged': False}},
        'surfaces': {'cover_face': {'residue_fraction': 1, 'dry': False,
                                  'debris_count': 0, 'damaged': False}}}
    actions = [row(1, 'remove', {'part_id': 'cover'}, carried_body_ids=['old']),
               row(2, 'inspect', {'target': 'old'}, observation={'damaged': False}),
               row(3, 'clean', {'target': 'cover_face', 'protect_openings': True,
                               'oil': True, 'sealant': 'cam_holder_corners'}),
               row(4, 'install', {'part_id': 'cover'}, carried_body_ids=['old'])]
    return config, initial, actions


class RefitHistory(unittest.TestCase):
    def test_bad_then_correct_refit_remains_bad_at_first_event(self):
        c, s, a = example()
        a.insert(1, row(2, 'install', {'part_id': 'cover'}, carried_body_ids=['old']))
        a.insert(2, row(3, 'remove', {'part_id': 'cover'}, carried_body_ids=['old']))
        for index, event in enumerate(a, 1): event['seq'] = index
        value = cover_refits(c, s, a)['refits']
        self.assertFalse(value[2]['passed'])
        self.assertTrue(value[6]['passed'])
        self.assertEqual(value[2]['cycle_start'], 1)
        self.assertEqual(value[6]['cycle_start'], 3)

    def test_removal_starts_a_new_inspection_and_treatment_cycle(self):
        c, s, a = example()
        a += [row(5, 'remove', {'part_id': 'cover'}, carried_body_ids=['old']),
              row(6, 'install', {'part_id': 'cover'}, carried_body_ids=['old'])]
        value = cover_refits(c, s, a)['refits']
        self.assertTrue(value[4]['passed'])
        self.assertFalse(value[6]['passed'])

    def test_new_seal_requires_source_exchange_before_that_install(self):
        c, s, a = example()
        a[1] = row(2, 'remove', {'part_id': 'old'})
        a[-1] = row(4, 'install', {'part_id': 'new'})
        self.assertFalse(cover_refits(c, s, a)['refits'][4]['passed'])
        a.insert(2, row(3, 'replace', {'part_id': 'old', 'replacement_id': 'new'}))
        for index, event in enumerate(a, 1): event['seq'] = index
        value = cover_refits(c, s, a)['refits'][5]
        self.assertTrue(value['passed'])
        self.assertEqual(value['route'], 'new')

    def test_refused_inspection_and_late_treatment_cannot_supply_evidence(self):
        for field in ('inspection', 'treatment'):
            c, s, a = example()
            if field == 'inspection': a[1]['result']['ok'] = False
            else: a[2], a[3] = a[3], a[2]
            for index, event in enumerate(a, 1): event['seq'] = index
            self.assertFalse(next(iter(cover_refits(c, s, a)['refits'].values()))['passed'])

    def test_boolean_numbers_and_unprotected_or_abrasive_cleaning_fail(self):
        for value in (0, 1, None, 'false'):
            c, s, a = example(); a[1]['result']['observation']['damaged'] = value
            self.assertFalse(cover_refits(c, s, a)['refits'][4]['passed'])
        for field, value in (('oil', 1), ('protect_openings', False), ('method', 'abrasive_disc')):
            c, s, a = example(); a[2]['input'][field] = value
            self.assertFalse(cover_refits(c, s, a)['refits'][4]['passed'])

    def test_no_initial_state_means_unavailable_not_an_assumed_valid_refit(self):
        c, _, a = example()
        self.assertEqual(cover_refits(c, None, a),
                         {'available': False, 'reason': 'initial_state_missing', 'refits': {}})

    def test_absent_bolt_preparation_fails_but_installed_missing_observation_is_unknown(self):
        original = {'parts': {'bolt': {'location': 'assembly'}}, 'surfaces': {},
                    'bolts': {'bolt': dict(thread_clean=True, thread_oiled=True, washer_oiled=True)},
                    'gasket': {'type': 'selected', 'orientation': 'up'}}
        ref = {'final': original, 'actions': [], 'position_by_body': {'bolt': 'p'}}
        config = {'geometry': {'parts': [{'id': 'bolt', 'role': 'head_bolt'}]},
                  'policy': {'timing_tolerance_deg': 0.1}}
        final = deepcopy(original); final['parts']['bolt']['location'] = 'tray'
        final['timing'] = {'cam_phase_deg': 0, 'crank_phase_deg': 0}
        final['bolts']['bolt'] = {}
        for body, expected in ((None, False), ('bolt', None)):
            bolt = {'service_position': 'p', 'body_id': body, 'checks': {}}
            rows = checklist(ref, final, {}, {}, [], [bolt], {}, config, 0, [], 4, {})
            prep = [r for r in rows if r['item'].startswith('bolt/p/')]
            self.assertEqual(len(prep), 3)
            self.assertTrue(all(r['correct'] is expected for r in prep))


if __name__ == '__main__': unittest.main()
