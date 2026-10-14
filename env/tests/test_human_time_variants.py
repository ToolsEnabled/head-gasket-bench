"""Bounded value checks for variant human-time charging; no game execution."""
import copy
import itertools
import json
import unittest
from pathlib import Path

from hgj import human_time as timing

ROOT = Path(__file__).resolve().parents[1]
BASES = {"parts_bin": 30, "machine_head": 1200, "tension_belt": 120, "set_timing": 120,
         "prepare_condition": 30, "release_attachment": 30, "restore_attachment": 30}
ASSESSMENTS = {"wrong_part": ("replace", 30), "missed_measurement": ("measure", 60),
               "missed_inspection": ("inspect", 30), "wrong_service_decision": ("inspect", 30),
               "missed_belt_tension": ("check_timing", 120)}


def labor():
    return json.loads((ROOT / "data" / "labor-v2.json").read_bytes())


def policy():
    return timing.policy_from_variant_labor(labor())


class VariantHumanTimeTests(unittest.TestCase):
    def assert_gate(self, gate, call):
        with self.assertRaises(timing.HumanTimeError) as context:
            call()
        self.assertEqual(context.exception.gate, gate)
        self.assertTrue(str(context.exception).strip())

    def assert_sum(self, row):
        self.assertEqual(row["total_seconds"], row["productive_seconds"] + row["penalty_seconds"])
        self.assertEqual(sum(x["seconds"] for x in row["penalties"]), row["penalty_seconds"])
        self.assertTrue(all(type(x["seconds"]) is int and x["seconds"] >= 0 for x in row["penalties"]))
        self.assertGreater(row["total_seconds"], 0)
        self.assertTrue(row["citations"])
        self.assertTrue(row["qualification"].strip())

    # test_legacy_factory_and_saved_policy_remain_equal: dropped; it compared against the v1 labor table / sandbox evidence that are not shipped.

    # test_extended_table_retains_all_original_action_rows: dropped; it compared against the v1 labor table / sandbox evidence that are not shipped.

    def test_saved_variant_policy_matches_factory_values_and_charges(self):
        saved = json.loads((ROOT / "data" / "human-time-policy-v3.json").read_bytes())
        generated = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        self.assertEqual(saved, generated)
        for name in BASES:
            for ok in (False, True):
                self.assertEqual(timing.charge(saved, name, ok=ok), timing.charge(generated, name, ok=ok))

    def test_new_bases_charge_success_and_refusal_without_free_attempts(self):
        value = policy()
        for name, seconds in BASES.items():
            for ok in (True, False):
                with self.subTest(action=name, ok=ok):
                    row = timing.charge(value, name, ok=ok)
                    self.assertTrue(row["action_known"])
                    self.assertEqual(row["base_seconds"], seconds)
                    self.assertEqual((row["productive_seconds"], row["penalty_seconds"]),
                                     (seconds, 0) if ok else (0, seconds))
                    self.assertEqual(row["mistake_event_count"], 0)
                    self.assert_sum(row)

    def test_canonical_assessments_are_cited_basis_values(self):
        value = policy()
        for name, (basis, seconds) in ASSESSMENTS.items():
            row = timing.penalty(value, name)
            self.assertEqual((row["type"], row["basis_action"], row["seconds"]), (name, basis, seconds))
            self.assertEqual(row["source_ids"], value["actions"][basis]["source_ids"])
            self.assertEqual(set(row["source_ids"]), {x["source_id"] for x in row["citations"]})
            self.assertTrue(row["qualification"].strip())

    def test_wrong_part_base_is_executed_wrong_work(self):
        row = timing.charge(policy(), "replace", ok=True, mistake_types=["wrong_part"])
        self.assertEqual((row["productive_seconds"], row["executed_wrong_work_seconds"],
                          row["assessment_seconds"], row["penalty_seconds"]), (0, 30, 30, 60))
        self.assert_sum(row)

    def test_wrong_service_decision_base_is_executed_wrong_work(self):
        row = timing.charge(policy(), "machine_head", ok=True, mistake_types=["wrong_service_decision"])
        self.assertEqual((row["productive_seconds"], row["executed_wrong_work_seconds"],
                          row["assessment_seconds"], row["penalty_seconds"]), (0, 1200, 30, 1230))
        self.assert_sum(row)

    def test_detection_only_missed_labels_keep_productive_inspection_base(self):
        for name, (_, seconds) in ASSESSMENTS.items():
            if name.startswith("missed_"):
                with self.subTest(type=name):
                    row = timing.charge(policy(), "finish", ok=True, mistake_types=[name])
                    self.assertEqual((row["productive_seconds"], row["executed_wrong_work_seconds"],
                                      row["assessment_seconds"]), (120, 0, seconds))
                    self.assert_sum(row)

    def test_overlapping_labels_and_duplicates_share_one_assessment(self):
        value = policy()
        labels = ["wrong_part", "missed_measurement", "missed_belt_tension", "wrong_part"]
        rows = [timing.charge(value, "replace", ok=True, mistake_types=list(x))
                for x in itertools.permutations(labels)]
        self.assertTrue(all(x == rows[0] for x in rows))
        row = rows[0]
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"]), (0, 150))
        self.assertEqual((row["executed_wrong_work_seconds"], row["assessment_seconds"]), (30, 120))
        self.assertEqual(row["mistake_event_count"], 1)
        self.assertEqual(len(row["mistake_types"]), 3)
        self.assert_sum(row)

    def test_refusal_overlapping_assessment_and_later_attempt_are_charged_once_each(self):
        value = policy()
        row = timing.charge(value, "parts_bin", ok=False,
                            mistake_types=["wrong_part", "missed_measurement", "missed_measurement"])
        self.assertEqual((row["penalty_seconds"], row["assessment_seconds"]), (60, 30))
        self.assert_sum(row)
        environmental = timing.charge(value, "machine_head", ok=False)
        self.assertEqual((environmental["productive_seconds"], environmental["penalty_seconds"],
                          environmental["mistake_event_count"]), (0, 1200, 0))
        repeated = [timing.charge(value, "replace", ok=True, mistake_types=["wrong_part"]) for _ in range(2)]
        self.assertEqual(sum(x["total_seconds"] for x in repeated), 120)
        self.assertEqual(sum(x["mistake_event_count"] for x in repeated), 2)

    def test_variant_factory_requires_explicit_complete_labor(self):
        value = labor()
        for flag in (None, 0, 1, "yes"):
            with self.subTest(flag=flag):
                self.assert_gate("human_time_variant_labor",
                                 lambda: timing.policy_from_labor(value, include_variant_types=flag))
        for action in BASES:
            damaged = labor(); damaged["actions"].pop(action)
            with self.subTest(missing=action):
                self.assert_gate("human_time_variant_labor",
                                 lambda: timing.policy_from_variant_labor(damaged))

    def test_source_adapter_rows_are_required_by_explicit_factory(self):
        for action in ("prepare_condition", "release_attachment", "restore_attachment"):
            damaged = labor()
            damaged["actions"].pop(action)
            with self.subTest(missing=action):
                self.assert_gate("human_time_variant_labor",
                                 lambda: timing.policy_from_variant_labor(damaged))

    def test_variant_action_bases_require_positive_bounded_integer_values(self):
        for action in BASES:
            for seconds in (0, -1, True, 1.0, timing.MAX_SECONDS + 1):
                with self.subTest(action=action, seconds=seconds):
                    value = policy(); value["actions"][action]["seconds"] = seconds
                    self.assert_gate("human_time_bounds", lambda: timing.validate_policy(value))

    def test_variant_citations_and_qualification_cannot_be_missing(self):
        for action in BASES:
            for ids in ([], ["UNKNOWN"], ["S1", "S1"]):
                value = policy(); value["actions"][action]["source_ids"] = ids
                with self.subTest(action=action, ids=ids):
                    self.assert_gate("human_time_citations", lambda: timing.validate_policy(value))
            for key in ("qualification", "rationale"):
                value = policy(); value["actions"][action][key] = ""
                with self.subTest(action=action, key=key):
                    self.assert_gate("human_time_qualification", lambda: timing.validate_policy(value))
        value = labor(); value["sources"]["S7"]["sha256"] = "invalid"
        self.assert_gate("human_time_citations", lambda: timing.policy_from_variant_labor(value))

    def test_variant_time_estimates_cannot_be_promoted_to_measured_or_physical(self):
        for key, replacement in (("duration_evidence", "measured"), ("published_standard", True),
                                 ("physical_acceptance", True)):
            value = policy(); value[key] = replacement
            with self.subTest(key=key):
                self.assert_gate("human_time_semantics", lambda: timing.validate_policy(value))

    def test_variant_call_input_errors_are_named_refusals(self):
        value = policy()
        for ok, names in ((1, []), (True, ["not_a_type"]), (True, "wrong_part")):
            with self.subTest(ok=ok, names=names):
                self.assert_gate("human_time_input",
                                 lambda: timing.charge(value, "parts_bin", ok=ok, mistake_types=names))

    def test_changed_cited_basis_values_are_used_instead_of_fixed_penalty_rates(self):
        value = labor()
        for action, seconds in (("replace", 37), ("measure", 91), ("check_timing", 203)):
            value["actions"][action]["seconds"] = seconds
        prepared = timing.policy_from_variant_labor(value)
        self.assertEqual(timing.penalty(prepared, "wrong_part")["seconds"], 37)
        self.assertEqual(timing.penalty(prepared, "missed_measurement")["seconds"], 91)
        self.assertEqual(timing.penalty(prepared, "missed_belt_tension")["seconds"], 203)
        row = timing.charge(prepared, "replace", ok=True, mistake_types=["wrong_part"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"]), (0, 74))
        self.assert_sum(row)

    def test_zero_assessment_never_makes_new_actions_free(self):
        value = policy()
        value["mistakes"]["wrong_service_decision"]["seconds"] = 0
        for ok in (False, True):
            row = timing.charge(value, "machine_head", ok=ok, mistake_types=["wrong_service_decision"])
            self.assertEqual((row["productive_seconds"], row["penalty_seconds"]), (0, 1200))
            self.assert_sum(row)
        unknown = timing.charge(value, "unknown_request", ok=False)
        self.assertEqual(unknown["total_seconds"], 10)
        self.assert_sum(unknown)

    def test_variant_gate_witnesses(self):
        witnesses = []
        witnesses.append(("human_time_variant_labor",
                          lambda: timing.policy_from_labor(labor(), include_variant_types=1)))
        for gate, mutate in (
            ("human_time_bounds", lambda p: p["actions"]["set_timing"].update(seconds=0)),
            ("human_time_citations", lambda p: p["actions"]["parts_bin"].update(source_ids=[])),
            ("human_time_citations", lambda p: p["sources"]["S7"].update(source_document_sha256="invalid")),
            ("human_time_qualification", lambda p: p["actions"]["machine_head"].update(qualification="")),
            ("human_time_semantics", lambda p: p.update(physical_acceptance=True)),
        ):
            value = policy()
            mutate(value)
            witnesses.append((gate, lambda value=value: timing.validate_policy(value)))
        value = policy()
        witnesses.append(("human_time_input",
                          lambda: timing.charge(value, "parts_bin", ok=1)))
        for gate, call in witnesses:
            with self.subTest(gate=gate):
                self.assert_gate(gate, call)

    def test_inputs_are_unchanged_and_return_values_detached(self):
        value = labor(); before = copy.deepcopy(value)
        prepared = timing.policy_from_variant_labor(value)
        self.assertEqual(value, before)
        snapshot = copy.deepcopy(prepared)
        row = timing.penalty(prepared, "wrong_part")
        row["citations"][0]["source_id"] = "changed"
        row["source_ids"].clear()
        labels = ["wrong_part", "wrong_part"]
        timing.charge(prepared, "replace", ok=True, mistake_types=labels)
        self.assertEqual(prepared, snapshot)
        self.assertEqual(labels, ["wrong_part", "wrong_part"])


    # test_default_variant_policy_retains_historical_seventeen_types: dropped; it compared against the v1 labor table / sandbox evidence that are not shipped.

    def test_restoration_policy_is_explicit_and_cited(self):
        value = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        self.assertEqual((len(value["actions"]), len(value["mistakes"])), (18, 18))
        row = timing.penalty(value, "missing_attachment_restore")
        self.assertEqual((row["basis_action"], row["seconds"]), ("restore_attachment", 30))
        self.assertEqual(row["source_ids"], value["actions"]["restore_attachment"]["source_ids"])
        self.assertEqual(set(row["source_ids"]), {x["source_id"] for x in row["citations"]})
        changed = labor(); changed["actions"]["restore_attachment"]["seconds"] = 43
        prepared = timing.policy_from_variant_labor(changed, include_attachment_restore=True)
        self.assertEqual(timing.penalty(prepared, "missing_attachment_restore")["seconds"], 43)

    def test_missing_restoration_detection_keeps_finish_productive(self):
        value = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        row = timing.charge(value, "finish", ok=True, mistake_types=["missing_attachment_restore"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"], row["total_seconds"]), (120, 30, 150))
        self.assertEqual(row["executed_wrong_work_seconds"], 0)
        self.assert_sum(row)
        second = timing.charge(value, "finish", ok=True, mistake_types=["missing_attachment_restore"])
        self.assertEqual(row, second)
        self.assertEqual(row["total_seconds"] + second["total_seconds"], 300)

    def test_restoration_labels_share_one_assessment_and_refused_base(self):
        value = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        row = timing.charge(value, "finish", ok=True,
                            mistake_types=["missing_attachment_restore", "missing_torque_stage",
                                           "missing_attachment_restore"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"]), (120, 30))
        self.assertEqual(row["mistake_event_count"], 1)
        self.assertEqual(len(row["mistake_types"]), 2)
        self.assert_sum(row)
        row = timing.charge(value, "finish", ok=False,
                            mistake_types=["missing_attachment_restore", "missing_torque_stage"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"], row["total_seconds"]), (0, 120, 120))
        self.assert_sum(row)
        value["mistakes"]["missing_attachment_restore"]["seconds"] = 0
        row = timing.charge(value, "finish", ok=True, mistake_types=["missing_attachment_restore"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"], row["total_seconds"]), (120, 0, 120))
        self.assert_sum(row)

    def test_restoration_opt_in_and_policy_epoch_are_strict(self):
        for flag in (None, 0, 1, "yes"):
            with self.subTest(flag=flag):
                self.assert_gate("human_time_restoration_epoch", lambda:
                                 timing.policy_from_variant_labor(labor(), include_attachment_restore=flag))
        self.assert_gate("human_time_restoration_epoch", lambda:
                         timing.policy_from_labor(labor(), include_attachment_restore=True))

    def test_restoration_policy_epoch_is_strict(self):
        value = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        for marker in (None, 0, "other"):
            changed = copy.deepcopy(value)
            if marker is None:
                changed.pop("mistake_epoch")
            else:
                changed["mistake_epoch"] = marker
            with self.subTest(marker=marker):
                self.assert_gate("human_time_restoration_epoch", lambda: timing.validate_policy(changed))
        changed = policy(); changed["mistake_epoch"] = value["mistake_epoch"]
        self.assert_gate("human_time_restoration_epoch", lambda: timing.validate_policy(changed))

    def test_restoration_row_retains_citations_qualification_and_estimate_scope(self):
        value = timing.policy_from_variant_labor(labor(), include_attachment_restore=True)
        for key, replacement, gate in (
            ("source_ids", [], "human_time_citations"),
            ("qualification", "", "human_time_qualification"),
            ("rationale", "", "human_time_qualification"),
            ("seconds", -1, "human_time_bounds"),
        ):
            changed = copy.deepcopy(value); changed["mistakes"]["missing_attachment_restore"][key] = replacement
            with self.subTest(key=key):
                self.assert_gate(gate, lambda: timing.validate_policy(changed))
        for key, replacement in (("published_standard", True), ("physical_acceptance", True)):
            changed = copy.deepcopy(value); changed[key] = replacement
            self.assert_gate("human_time_semantics", lambda: timing.validate_policy(changed))


if __name__ == "__main__":
    unittest.main()
