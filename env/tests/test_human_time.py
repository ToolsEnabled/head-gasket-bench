"""Human-time behavior using public labor metadata; no jobs or model execution."""
import copy
import itertools
import json
import unittest
from pathlib import Path

from hgj import human_time as timing

ROOT = Path(__file__).resolve().parents[1]


def labor():
    return json.loads((ROOT / "data" / "labor-v2.json").read_text(encoding="utf-8"))


def policy():
    return timing.policy_from_labor(labor())


def gate_witnesses():
    rows = []
    for gate, damage in (
        ("human_time_shape", lambda value: value.update(schema="unsupported")),
        ("human_time_bounds", lambda value: value["actions"]["look"].update(seconds=0)),
        ("human_time_citations", lambda value: value["actions"]["look"].update(source_ids=[])),
        ("human_time_qualification", lambda value: value["actions"]["look"].update(qualification="")),
        ("human_time_semantics", lambda value: value.update(published_standard=True)),
    ):
        value = policy()
        damage(value)
        rows.append((gate, lambda value=value: timing.validate_policy(value)))
    value = labor()
    value["scope"] = ""
    rows.append(("human_time_labor", lambda value=value: timing.policy_from_labor(value)))
    value = policy()
    rows.append(("human_time_input",
                 lambda value=value: timing.charge(value, "look", ok=1, mistake_types=[])))
    return rows


class HumanTimeTests(unittest.TestCase):
    def assert_gate(self, gate, call):
        with self.assertRaises(timing.HumanTimeError) as context:
            call()
        self.assertEqual(context.exception.gate, gate)
        self.assertTrue(str(context.exception).strip())

    def assert_sum(self, value):
        self.assertEqual(value["total_seconds"], value["productive_seconds"] + value["penalty_seconds"])
        self.assertEqual(sum(row["seconds"] for row in value["penalties"]), value["penalty_seconds"])
        self.assertTrue(all(type(row["seconds"]) is int and row["seconds"] >= 0 for row in value["penalties"]))
        self.assertGreater(value["total_seconds"], 0)
        self.assertTrue(value["citations"])

    def test_complete_labor_table_bases_and_qualifications_retained(self):
        original = labor()
        prepared = timing.policy_from_labor(original)
        self.assertEqual(set(prepared["actions"]), set(original["actions"]))
        self.assertEqual(set(prepared["sources"]), set(original["sources"]))
        for name, row in original["actions"].items():
            with self.subTest(action=name):
                self.assertEqual(prepared["actions"][name]["seconds"], row["seconds"])
                self.assertEqual(prepared["actions"][name]["source_ids"], row["source_ids"])
                self.assertEqual(prepared["actions"][name]["qualification"], row["qualification"])
                success = timing.charge(prepared, name, ok=True, mistake_types=[])
                refusal = timing.charge(prepared, name, ok=False, mistake_types=[])
                self.assertEqual((success["productive_seconds"], success["penalty_seconds"]), (row["seconds"], 0))
                self.assertEqual((refusal["productive_seconds"], refusal["penalty_seconds"]), (0, row["seconds"]))
                self.assert_sum(success); self.assert_sum(refusal)

    def test_delivered_policy_matches_factory_charging_behavior(self):
        saved = json.loads((ROOT / "data" / "human-time-policy-v3.json").read_text())
        generated = policy()
        for name in generated["actions"]:
            for ok in (False, True):
                with self.subTest(action=name, ok=ok):
                    self.assertEqual(timing.charge(saved, name, ok=ok),
                                     timing.charge(generated, name, ok=ok))

    def test_unknown_attempts_have_a_positive_cited_fallback(self):
        value = policy()
        for ok in (False, True):
            charged = timing.charge(value, "unsupported_tool", ok=ok)
            self.assertFalse(charged["action_known"])
            self.assertEqual(charged["total_seconds"], 10)
            self.assert_sum(charged)

    def test_deterministic_values_and_no_mutation_of_inputs(self):
        value = policy(); before = copy.deepcopy(value)
        labels = ["wrong_gasket", "wrong_torque_value", "wrong_gasket"]
        original = list(labels)
        results = [timing.charge(value, "torque", ok=True, mistake_types=list(order))
                   for order in itertools.permutations(labels)]
        self.assertTrue(all(row == results[0] for row in results))
        self.assertEqual(results[0]["productive_seconds"], 0)
        self.assertEqual(results[0]["penalty_seconds"], 42)
        self.assertEqual(results[0]["total_seconds"], 42)
        self.assertEqual(results[0]["mistake_event_count"], 1)
        self.assertEqual(value, before); self.assertEqual(labels, original)
        validated = timing.validate_policy(value)
        validated["actions"]["look"]["seconds"] = 999
        self.assertEqual(value, before)

    def test_same_event_labels_share_charge_and_refusal_base_is_not_repeated(self):
        value = policy()
        charged = timing.charge(value, "remove", ok=False,
                                mistake_types=["blocked_removal", "wrong_order", "blocked_removal"])
        self.assertEqual((charged["productive_seconds"], charged["penalty_seconds"]), (0, 30))
        self.assertEqual(charged["mistake_types"], ["blocked_removal", "wrong_order"])
        self.assertEqual(charged["mistake_event_count"], 1)
        self.assertEqual(sum(row["seconds"] for row in charged["penalties"] if row["is_mistake"]), 0)
        self.assert_sum(charged)
        higher = timing.charge(value, "remove", ok=False, mistake_types=["timing_marks_off"])
        self.assertEqual(higher["penalty_seconds"], 120)
        self.assertEqual([row["seconds"] for row in higher["penalties"]], [30, 90])
        self.assert_sum(higher)

    def test_distinct_events_do_not_share_a_global_deduplication_set(self):
        value = policy()
        repeated = [timing.charge(value, "torque", ok=True, mistake_types=["missing_torque_stage"])
                    for _ in range(10)]
        self.assertEqual(sum(row["total_seconds"] for row in repeated), 240)
        self.assertEqual(sum(row["mistake_event_count"] for row in repeated), 10)
        grouped = timing.charge(value, "torque", ok=True,
                                mistake_types=["missing_torque_stage"] * 10)
        self.assertEqual(grouped["total_seconds"], 24)
        self.assertEqual(grouped["mistake_event_count"], 1)
        self.assertEqual(grouped["mistake_types"], ["missing_torque_stage"])

    def test_environmental_refusal_is_charged_without_inventing_a_mechanic_error(self):
        charged = timing.charge(policy(), "search_service_info", ok=False, mistake_types=[])
        self.assertEqual(charged["total_seconds"], 30)
        self.assertEqual(charged["mistake_event_count"], 0)
        self.assertEqual(charged["mistake_types"], [])
        self.assertEqual(len(charged["penalties"]), 1)
        self.assertFalse(charged["penalties"][0]["is_mistake"])
        self.assert_sum(charged)

    def test_canonical_types_alias_lookup_and_cited_rows(self):
        value = policy()
        expected = {"blocked_removal", "wrong_order", "wrong_torque_value", "wrong_torque_stage",
                    "missing_torque_stage", "wrong_gasket", "wrong_orientation",
                    "reused_stretched_bolt", "timing_marks_off", "missed_lookup", "redo_work", "invalid_action"}
        self.assertEqual(set(value["mistakes"]), expected)
        for name in expected:
            row = timing.penalty(value, name)
            self.assertEqual(row["type"], name)
            self.assertGreaterEqual(row["seconds"], 0)
            self.assertTrue(row["citations"])
            self.assertEqual(set(row["source_ids"]), {entry["source_id"] for entry in row["citations"]})
            self.assertTrue(row["qualification"].strip())
        canonical = timing.charge(value, "torque", ok=True, mistake_types=["wrong_torque_value"])
        aliases = timing.charge(value, "torque", ok=True,
                                mistake_types=["wrong_torque", "under_torque", "wrong_torque_value"])
        self.assertEqual(canonical, aliases)
        self.assertEqual(timing.penalty(value, "under_torque")["type"], "wrong_torque_value")
        self.assert_gate("human_time_input", lambda: timing.penalty(value, "unrecognized"))

    def test_explicit_missing_or_unresolving_citations_are_refused(self):
        for ids in ([], ["MISSING"], ["S7", "S7"]):
            with self.subTest(ids=ids):
                value = policy(); value["actions"]["look"]["source_ids"] = ids
                self.assert_gate("human_time_citations", lambda: timing.validate_policy(value))
        for change in (lambda row: row.pop("labor_source_record_sha256"),
                       lambda row: row.update(source_document_sha256="invalid"),
                       lambda row: row.update(reference="synthetic reference marker")):
            value = policy(); change(value["sources"]["S7"])
            self.assert_gate("human_time_citations", lambda: timing.validate_policy(value))

    def test_factory_exports_neutral_hashes_instead_of_source_reference_text(self):
        original = labor()
        original["sources"]["S7"]["reference"] = "synthetic reference marker"
        original["sources"]["S7"]["sha256"] = "a" * 64   # a synthetic document hash
        original["sources"]["S1"]["locator"] = "synthetic locator marker"
        value = timing.policy_from_labor(original)
        serialized = json.dumps(value)
        self.assertNotIn("synthetic reference marker", serialized)
        self.assertNotIn("synthetic locator marker", serialized)
        self.assertIn("source_document_sha256", value["sources"]["S7"])
        for row in value["sources"].values():
            self.assertTrue(set(row) <= {"source_id", "labor_source_record_sha256", "source_document_sha256"})

    def test_zero_negative_boolean_float_and_oversized_bases_are_rejected(self):
        for seconds in (0, -1, True, 1.0, float("nan"), float("inf"), timing.MAX_SECONDS + 1):
            with self.subTest(seconds=seconds):
                value = policy(); value["actions"]["look"]["seconds"] = seconds
                self.assert_gate("human_time_bounds", lambda: timing.validate_policy(value))
                value = policy(); value["unknown_action"]["seconds"] = seconds
                self.assert_gate("human_time_bounds", lambda: timing.validate_policy(value))

    def test_zero_assessment_is_allowed_but_never_makes_an_attempt_free(self):
        value = policy(); value["mistakes"]["wrong_torque_value"]["seconds"] = 0
        success = timing.charge(value, "torque", ok=True, mistake_types=["wrong_torque_value"])
        refusal = timing.charge(value, "torque", ok=False, mistake_types=["wrong_torque_value"])
        self.assertEqual(success["total_seconds"], 12); self.assertEqual(refusal["total_seconds"], 12)
        self.assert_sum(success); self.assert_sum(refusal)
        value["mistakes"]["wrong_torque_value"]["seconds"] = -1
        self.assert_gate("human_time_bounds", lambda: timing.validate_policy(value))

    def test_invalid_call_values_and_input_bounds_are_named_refusals(self):
        value = policy()
        cases = [("", True, []), (None, True, []), ("look", 1, []),
                 ("look", True, "wrong_order"), ("look", True, {"wrong_order"}),
                 ("look", True, [None]), ("look", True, ["unknown"]),
                 ("look", True, ["wrong_order"] * (timing.MAX_INPUT_LABELS + 1)),
                 ("x" * (timing.MAX_NAME_LENGTH + 1), True, [])]
        for name, ok, types in cases:
            with self.subTest(name=name, ok=ok, types_type=type(types).__name__):
                self.assert_gate("human_time_input",
                                 lambda: timing.charge(value, name, ok=ok, mistake_types=types))

    def test_policy_bounds_semantics_and_qualifications_are_enforced(self):
        for change, gate in [
            (lambda value: value.update(physical_acceptance=True), "human_time_semantics"),
            (lambda value: value.update(duration_evidence="measured"), "human_time_semantics"),
            (lambda value: value.update(base_classification="all success productive"), "human_time_semantics"),
            (lambda value: value.update(aliases={"alias": []}), "human_time_semantics"),
            (lambda value: value.update(aliases={"wrong_order": "wrong_order"}), "human_time_semantics"),
            (lambda value: value.update(qualification=""), "human_time_qualification"),
            (lambda value: value["mistakes"]["wrong_order"].update(rationale=""), "human_time_qualification"),
            (lambda value: value["mistakes"]["wrong_order"].update(basis_action="unknown"), "human_time_semantics"),
            (lambda value: value.update(sources={}), "human_time_shape"),
        ]:
            with self.subTest(gate=gate):
                value = policy(); change(value)
                self.assert_gate(gate, lambda: timing.validate_policy(value))

    def test_factory_bad_metadata_and_missing_basis_are_explicit_refusals(self):
        for change in (lambda value: value["sources"]["S7"].update(extra=float("nan")),
                       lambda value: value["sources"]["S7"].update(extra={1, 2}),
                       lambda value: value["actions"].pop("look"),
                       lambda value: value.update(scope="")):
            original = labor(); change(original)
            self.assert_gate("human_time_labor", lambda: timing.policy_from_labor(original))

    def test_successful_wrong_work_base_is_penalty_and_total_is_preserved(self):
        value = policy()
        for name in ("wrong_order", "wrong_torque_value", "wrong_torque_stage", "wrong_gasket",
                     "wrong_orientation", "reused_stretched_bolt", "timing_marks_off", "redo_work"):
            with self.subTest(type=name):
                row = timing.charge(value, "torque", ok=True, mistake_types=[name])
                allowance = value["mistakes"][name]["seconds"]
                self.assertEqual(row["productive_seconds"], 0)
                self.assertEqual(row["penalty_seconds"], 12 + allowance)
                self.assertEqual(row["total_seconds"], 12 + allowance)
                self.assertEqual(row["executed_wrong_work_seconds"], 12)
                self.assertEqual(row["assessment_seconds"], allowance)
                self.assertEqual(row["mistake_event_count"], 1)
                self.assertEqual(row["penalties"][0]["seconds"], 12)
                self.assertFalse(row["penalties"][0]["is_mistake"])
                self.assert_sum(row)

    def test_detection_only_success_retains_productive_base_and_mixed_wrong_work_does_not(self):
        value = policy()
        for names in (["missing_torque_stage"], ["missed_lookup"],
                      ["missing_torque_stage", "missed_lookup"]):
            with self.subTest(types=names):
                row = timing.charge(value, "finish", ok=True, mistake_types=names)
                self.assertEqual(row["productive_seconds"], value["actions"]["finish"]["seconds"])
                self.assertEqual(row["executed_wrong_work_seconds"], 0)
                self.assert_sum(row)
        row = timing.charge(value, "torque", ok=True,
                            mistake_types=["missed_lookup", "wrong_torque_value", "wrong_torque"])
        self.assertEqual(row["productive_seconds"], 0)
        self.assertEqual(row["penalty_seconds"], 42)
        self.assertEqual(row["total_seconds"], 42)
        self.assertEqual(row["mistake_event_count"], 1)
        self.assert_sum(row)
        value["mistakes"]["wrong_torque_value"]["seconds"] = 0
        row = timing.charge(value, "torque", ok=True, mistake_types=["wrong_torque_value"])
        self.assertEqual((row["productive_seconds"], row["penalty_seconds"]), (0, 12))
        self.assert_sum(row)

    def test_gate_witnesses_rejected(self):
        for gate, call in gate_witnesses():
            with self.subTest(gate=gate):
                self.assert_gate(gate, call)


if __name__ == "__main__":
    unittest.main()
