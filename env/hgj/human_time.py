"""Deterministic human-time charges from cited, qualified analyst estimates.

No clock, scorer, model or source file is executed here. One call represents one
action attempt. Labels describing the same mistake event share one time charge.
"""
import copy
import hashlib
import json
import re

SCHEMA = "hgj/human-time-policy/v1"
MAX_SECONDS = 86400
MAX_ACTIONS = 64
MAX_SOURCES = 64
MAX_TYPES = 32
MAX_INPUT_LABELS = 128
MAX_NAME_LENGTH = 256
QUALIFICATION = ("Cited analyst professional-task estimates; not measured technician time "
                 "or a published labor-time standard.")
AGGREGATION = "maximum assessment estimate per action attempt; refused base included once"
BASE_CLASSIFICATION = "successful correct work is productive; executed wrong work base is penalty"
EXECUTED_WRONG_TYPES = frozenset({
    "wrong_order", "wrong_torque_value", "wrong_torque_stage", "wrong_gasket",
    "wrong_orientation", "reused_stretched_bolt", "timing_marks_off", "redo_work",
    "wrong_part", "wrong_service_decision",
})


def _executed_wrong_work(types):
    return bool(EXECUTED_WRONG_TYPES.intersection(types))

# Assessment/recheck allowances reuse one cited operation as their planning unit.
# The actual corrective action, if attempted later, receives its own base charge.
LEGACY_MISTAKE_BASES = {
    "blocked_removal": "remove",
    "wrong_order": "remove",
    "wrong_torque_value": "torque",
    "wrong_torque_stage": "torque",
    "missing_torque_stage": "torque",
    "wrong_gasket": "replace",
    "wrong_orientation": "install",
    "reused_stretched_bolt": "replace",
    "timing_marks_off": "check_timing",
    "missed_lookup": "search_service_info",
    "redo_work": "inspect",
    "invalid_action": "look",
}
VARIANT_MISTAKE_BASES = {
    "wrong_part": "replace",
    "missed_measurement": "measure",
    "missed_inspection": "inspect",
    "wrong_service_decision": "inspect",
    "missed_belt_tension": "check_timing",
}
RESTORATION_MISTAKE_BASES = {"missing_attachment_restore": "restore_attachment"}
RESTORATION_EPOCH = "variant-restoration-v1"
MISTAKE_BASES = {**LEGACY_MISTAKE_BASES, **VARIANT_MISTAKE_BASES, **RESTORATION_MISTAKE_BASES}
VARIANT_ACTIONS = frozenset({
    "parts_bin", "machine_head", "tension_belt", "set_timing",
    "prepare_condition", "release_attachment", "restore_attachment",
})
ALIASES = {
    "wrong_removal_order": "wrong_order",
    "wrong_installation": "redo_work",
    "wrong_torque": "wrong_torque_value",
    "wrong_torque_sequence": "wrong_order",
    "under_torque": "wrong_torque_value",
    "skipped_final_stage": "missing_torque_stage",
    "wrong_timing": "timing_marks_off",
    "invalid_argument": "invalid_action",
}


class HumanTimeError(ValueError):
    def __init__(self, gate, reason):
        self.gate = gate
        super().__init__(gate + ": " + reason)


def require(condition, gate, reason):
    if not condition:
        raise HumanTimeError(gate, reason)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(value):
    try:
        return hashlib.sha256(_canonical(value)).hexdigest()
    except (TypeError, ValueError, OverflowError) as error:
        raise HumanTimeError("human_time_labor", "labor metadata must be finite, serializable JSON") from error


def _text(value):
    return type(value) is str and bool(value.strip())


def _key(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value) is not None


def _hash(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _row(row, sources, *, productive):
    require(type(row) is dict, "human_time_shape", "time row must be an object")
    seconds = row.get("seconds")
    require(type(seconds) is int and (1 if productive else 0) <= seconds <= MAX_SECONDS,
            "human_time_bounds", "base seconds must be positive; assessment seconds nonnegative and bounded")
    ids = row.get("source_ids")
    require(type(ids) is list and 0 < len(ids) <= MAX_SOURCES
            and all(_key(value) and value in sources for value in ids)
            and len(ids) == len(set(ids)),
            "human_time_citations", "every time row requires distinct, resolving source citations")
    require(_text(row.get("qualification")) and _text(row.get("rationale")),
            "human_time_qualification", "time row must retain a qualification and explicit estimate rationale")
    return row


def validate_policy(policy):
    """Return a detached validated policy; raise a named refusal on bad inputs."""
    require(type(policy) is dict and policy.get("schema") == SCHEMA
            and type(policy.get("actions")) is dict and 0 < len(policy["actions"]) <= MAX_ACTIONS
            and all(_key(name) for name in policy["actions"])
            and type(policy.get("mistakes")) is dict and 0 < len(policy["mistakes"]) <= MAX_TYPES
            and all(_key(name) for name in policy["mistakes"])
            and type(policy.get("sources")) is dict and 0 < len(policy["sources"]) <= MAX_SOURCES
            and all(_key(name) for name in policy["sources"]),
            "human_time_shape", "invalid policy schema, names, collection types or census")
    require(policy.get("unit") == "seconds" and policy.get("aggregation") == AGGREGATION
            and policy.get("duration_evidence") == "analyst-estimated"
            and policy.get("base_classification") == BASE_CLASSIFICATION
            and policy.get("published_standard") is False
            and policy.get("physical_acceptance") is False
            and _hash(policy.get("labor_content_sha256"))
            and type(policy.get("aliases")) is dict and len(policy["aliases"]) <= MAX_TYPES
            and all(_key(name) and name not in policy["mistakes"]
                    and _key(target) and target in policy["mistakes"]
                    for name, target in policy["aliases"].items()),
            "human_time_semantics", "policy must preserve estimated duration and one-event charging scope")
    require(_text(policy.get("qualification")) and _text(policy.get("scope")),
            "human_time_qualification", "policy qualification and charging scope must be explicit")
    restoration = "missing_attachment_restore" in policy["mistakes"]
    require((restoration and policy.get("mistake_epoch") == RESTORATION_EPOCH)
            or (not restoration and "mistake_epoch" not in policy),
            "human_time_restoration_epoch",
            "attachment-restoration assessment requires its explicit policy epoch")
    sources = policy["sources"]
    for name, value in sources.items():
        require(type(value) is dict and set(value) <=
                {"source_id", "labor_source_record_sha256", "source_document_sha256"}
                and value.get("source_id") == name
                and _hash(value.get("labor_source_record_sha256"))
                and ("source_document_sha256" not in value or _hash(value["source_document_sha256"])),
                "human_time_citations", "source citation identity or neutral record/document hash missing")
    for row in policy["actions"].values():
        _row(row, sources, productive=True)
    _row(policy.get("unknown_action"), sources, productive=True)
    for row in policy["mistakes"].values():
        _row(row, sources, productive=False)
        require(_key(row.get("basis_action")) and row["basis_action"] in policy["actions"],
                "human_time_semantics", "assessment estimate must identify an existing cited operation")
    return copy.deepcopy(policy)


def policy_from_labor(labor, *, include_variant_types=False, include_attachment_restore=False):
    """Retain the complete table's bases without publishing them as standards.

    Source identities are neutral IDs and hashes; source text, references and
    locators are deliberately not copied into the generated policy. The default
    retains the legacy twelve mistake types. Variant assessments require an
    explicit opt-in and all seven cited variant operations.
    """
    require(type(include_variant_types) is bool,
            "human_time_variant_labor", "variant opt-in must be a boolean")
    require(not include_variant_types or
            (type(labor) is dict and type(labor.get("actions")) is dict
             and VARIANT_ACTIONS <= set(labor["actions"])),
            "human_time_variant_labor", "variant labor must supply all seven variant operations")
    require(type(include_attachment_restore) is bool
            and (not include_attachment_restore or include_variant_types),
            "human_time_restoration_epoch",
            "restoration opt-in must be a boolean and requires the variant policy")
    mistake_bases = {**LEGACY_MISTAKE_BASES, **VARIANT_MISTAKE_BASES} if include_variant_types else LEGACY_MISTAKE_BASES
    if include_attachment_restore:
        mistake_bases = {**mistake_bases, **RESTORATION_MISTAKE_BASES}
    require(type(labor) is dict and _text(labor.get("scope"))
            and type(labor.get("sources")) is dict
            and 0 < len(labor["sources"]) <= MAX_SOURCES
            and all(_key(name) and type(row) is dict for name, row in labor["sources"].items())
            and type(labor.get("actions")) is dict and 0 < len(labor["actions"]) <= MAX_ACTIONS
            and all(_key(name) and type(row) is dict for name, row in labor["actions"].items())
            and set(mistake_bases.values()) <= set(labor["actions"]),
            "human_time_labor", "labor table must supply source records and all assessment basis operations")
    sources = {}
    for name, row in labor["sources"].items():
        value = {"source_id": name, "labor_source_record_sha256": _digest(row)}
        if "sha256" in row:
            require(_hash(row["sha256"]), "human_time_citations", "source document hash invalid")
            value["source_document_sha256"] = row["sha256"]
        sources[name] = value
    actions = {
        name: {key: copy.deepcopy(row.get(key))
               for key in ("seconds", "source_ids", "qualification", "rationale")}
        for name, row in labor["actions"].items()
    }
    if "torque" in actions:
        actions["torque"]["rationale"] = (
            "Analyst estimate for one fastener tightening or loosening application. "
            "Procedure citations support the operation, not elapsed time; this is "
            "not a measured whole-job flat-rate standard.")
    mistakes = {}
    for name, action in mistake_bases.items():
        basis = actions[action]
        mistakes[name] = {
            "seconds": basis["seconds"], "source_ids": copy.deepcopy(basis["source_ids"]),
            "qualification": QUALIFICATION, "basis_action": action,
            "rationale": ("Analyst assessment/recheck allowance using one cited " + action
                          + " operation as a planning unit. Procedure citations establish the task, "
                            "not elapsed time. Overlapping labels share one allowance; a later "
                            "corrective action is charged separately when attempted."),
        }
    unknown = copy.deepcopy(actions["look"])
    unknown["rationale"] = ("Analyst allowance to assess an unsupported action request, using one cited "
                            "look operation. This positive base prevents uncharged unknown attempts; "
                            "it is not a measured or published technician-time standard.")
    policy = {
        "schema": SCHEMA, "unit": "seconds", "duration_evidence": "analyst-estimated",
        "published_standard": False, "physical_acceptance": False,
        "qualification": QUALIFICATION,
        "scope": ("Each action attempt is charged. Successful correct work is productive; successful "
                  "executed wrong/rework base and every refused base are penalty time. Missing "
                  "stage or missed lookup detected alone retains successful productive base. "
                  "Same-attempt typed assessments share the maximum allowance, inclusive of "
                  "refused base but separate from executed wrong work. Wall time is separate."),
        "base_classification": BASE_CLASSIFICATION,
        "aggregation": AGGREGATION, "labor_content_sha256": _digest(labor),
        "sources": sources, "actions": actions, "unknown_action": unknown, "mistakes": mistakes,
        "aliases": copy.deepcopy(ALIASES),
    }
    if include_variant_types:
        policy["scope"] += (
            " Variant wrong-part and wrong-service decisions are executed wrong work; "
            "missed measurement, inspection or belt tension detected alone keeps a "
            "successful inspection/finish base productive. Variant machining is a "
            "configured provisional service estimate, not physical repair admission.")
    if include_attachment_restore:
        policy["mistake_epoch"] = RESTORATION_EPOCH
        policy["scope"] += (
            " Missing attachment restoration detected at finish retains its productive base; "
            "the cited restoration assessment shares the same-event maximum allowance.")
    return validate_policy(policy)


def policy_from_variant_labor(labor, *, include_attachment_restore=False):
    """Build the additive variant policy only from an explicit extended table."""
    return policy_from_labor(labor, include_variant_types=True,
                             include_attachment_restore=include_attachment_restore)


def penalty(policy, mistake_type):
    """Return one cited assessment row; aliases resolve explicitly, without charging."""
    policy = validate_policy(policy)
    require(type(mistake_type) is str
            and (mistake_type in policy["mistakes"] or mistake_type in policy["aliases"]),
            "human_time_input", "unknown or invalid mistake type")
    name = policy["aliases"].get(mistake_type, mistake_type)
    row = copy.deepcopy(policy["mistakes"][name])
    return {"type": name, "requested_type": mistake_type, **row,
            "citations": [copy.deepcopy(policy["sources"][source]) for source in sorted(row["source_ids"])]}


def charge(policy, action_name, *, ok, mistake_types=()):
    """Charge one event once; multiple labels are overlapping assessments.

    Refused attempts always pay their base as penalty. Additional typed
    assessment adds only the amount above that base. Successful wrong/rework
    attempts move their base to penalty and still pay the separate maximum
    assessment; detection-only labels keep successful base productive. Equal-cost
    labels allocate once to the alphabetically first label; all labels/citations
    remain visible. A later repair attempt is a separate charged event.
    """
    policy = validate_policy(policy)
    require(type(action_name) is str and bool(action_name.strip())
            and len(action_name) <= MAX_NAME_LENGTH and type(ok) is bool
            and type(mistake_types) in (list, tuple) and len(mistake_types) <= MAX_INPUT_LABELS
            and all(type(value) is str and (value in policy["mistakes"] or value in policy["aliases"])
                    for value in mistake_types),
            "human_time_input", "action, result flag or typed mistake list is invalid")
    types = sorted({policy["aliases"].get(value, value) for value in mistake_types})
    known = action_name in policy["actions"]
    base = policy["actions"][action_name] if known else policy["unknown_action"]
    executed_wrong = base["seconds"] if ok and _executed_wrong_work(types) else 0
    productive = base["seconds"] if ok and not executed_wrong else 0
    refused = 0 if ok else base["seconds"]
    assessment = max((policy["mistakes"][name]["seconds"] for name in types), default=0)
    extra = max(refused, assessment) - refused
    penalty = refused + executed_wrong + extra
    winner = next((name for name in types if policy["mistakes"][name]["seconds"] == assessment), None)
    penalties = []
    if not ok:
        penalties.append({
            "type": "refused_attempt", "is_mistake": False,
            "seconds": refused, "estimated_seconds": refused,
            "source_ids": copy.deepcopy(base["source_ids"]),
            "qualification": base["qualification"],
            "reason": "Base of this refused attempt, charged once.",
        })
    if executed_wrong:
        penalties.append({
            "type": "executed_wrong_work", "is_mistake": False,
            "seconds": executed_wrong, "estimated_seconds": executed_wrong,
            "source_ids": copy.deepcopy(base["source_ids"]),
            "qualification": base["qualification"],
            "reason": "Base of successful wrong/rework operation; separate from assessment, charged once.",
        })
    ids = set(base["source_ids"])
    for name in types:
        row = policy["mistakes"][name]
        ids.update(row["source_ids"])
        applied = extra if name == winner else 0
        penalties.append({
            "type": name, "is_mistake": True,
            "seconds": applied, "estimated_seconds": row["seconds"],
            "source_ids": copy.deepcopy(row["source_ids"]), "qualification": row["qualification"],
            "reason": ("Shared assessment allowance beyond refused base, allocated once." if applied
                       else "Overlapping assessment label covered by this event's charge."),
        })
    return {
        "action_name": action_name, "action_known": known, "ok": ok,
        "productive_seconds": productive, "penalty_seconds": penalty,
        "total_seconds": productive + penalty, "base_seconds": base["seconds"],
        "executed_wrong_work_seconds": executed_wrong, "assessment_seconds": extra,
        "mistake_types": types, "mistake_event_count": 1 if types else 0,
        "citations": [copy.deepcopy(policy["sources"][name]) for name in sorted(ids)],
        "qualification": policy["qualification"], "base_qualification": base["qualification"],
        "penalties": penalties,
    }
