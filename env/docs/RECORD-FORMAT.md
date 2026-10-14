# Record format

All files are canonical JSON: keys sorted, no spaces, `ensure_ascii=False`,
one trailing newline (`hgj/codec.py`). A hash of a value means SHA-256 of
those bytes. The run folder is written by `hgj/mcp.py` and nothing else.

## run.json (`hgj/run/v2`)

| Field | Content |
|---|---|
| `schema` | `hgj/run/v2` |
| `environment_source` | Identity of the source that ran: `source_manifest_sha256`, `source_manifest_body_sha256`, the 18 `sources` with their hashes, the `bootstrap` loader hash, the interpreter (`cpython`, `[3, 12, 3]`, `cpython-312`) and qualification labels |
| `environment_source_sha256` | Hash of `environment_source` |
| `config` | The complete configuration the run used |
| `config_sha256` | Hash of `config`; equals the pin in `configs/PINS.json` |
| `initial_state`, `initial_state_sha256` | The captured starting mechanical state |
| `actions` | One row per attempt, in order (below) |
| `final_state`, `final_state_sha256` | The state after the last attempt |
| `score`, `score_sha256` | `hgj/repair-score/v1` (below) |
| `finished` | `true` only after a successful `finish` |
| `scoring_status` | `scored` or `in_progress` |
| `budget` | `{limit: 1024, unit: "job-tool-action-attempts", used, attempted_calls, exhausted}` |

### Action rows

| Field | Content |
|---|---|
| `seq` | 1-based position |
| `name`, `input` | The tool and its arguments exactly as received |
| `result` | The reply: `ok`, the observation or the refusal text, `turns_remaining` |
| `pre_state_sha256`, `post_state_sha256` | Hashes of the state before and after (equal for a refusal) |
| `previous_action_sha256` | Hash of the previous row; the first row carries `config_sha256` |
| `human_time_charge` | The charged seconds: base, productive, penalty, assessments, mistake types, citations |

The chain check is: `prev = config_sha256; for row in actions: assert row.previous_action_sha256 == prev; prev = sha256(canonical(row))`.
`python3 -m headgasket verify` performs it, then replays the actions and
compares the regenerated record with the file.

### score (`hgj/repair-score/v1`)

`primary_score` (the twelve checkpoints with `id`, `weight`, `passed`, and
`points_earned`, `total_points`, `S_full`, `S_partial`), `bolt_accuracy` and
`checklist_accuracy` (`correct`, `total`, `accuracy_percent`, items),
`mistakes` (`count`, `by_type`, events), `human_time` (`productive_seconds`,
`penalty_seconds`, `total_seconds`, `reference_seconds`, ledger),
`tool_calls`, `coverage`, `checkpoint_revision`, `reference_sha256`, `status`.

## actions.jsonl

The `actions` rows, one canonical line each. Identical bytes to joining the
rows of `run.json`.

## report.json (`hgj/repair-run-report/v1`)

`run_sha256` (hash of the record it describes), `score_sha256`, `finished`,
`status` (`finished`, `incomplete`, `in_progress`), `terminal_reason`
(`finished`, `budget_exhausted`, `tool_call_limit`,
`input_ended_without_finish`, `interrupted`, `transport_error`),
`real_time.seconds` from the server's monotonic clock, `tokens` (all `null`;
the server cannot see them), `tool_calls` (`attempted`, `successful`,
`refused`), and copies of the score summaries.

## finish-record.json

The complete `run.json` bytes at the moment `finish` succeeded. Later refused
calls can still be appended to `run.json`; the snapshot is never rewritten.
The `finish` reply names it: `{"record": {"file": "finish-record.json",
"sha256": ..., "bytes": ...}}`.

## launch.json (`headgasket/launch/v1`)

Written by the launcher after the server exits: launcher version, variant,
configuration path and hash, source manifest hash, interpreter, UTC start and
end, number of actions and whether the run finished. It is not part of the
record and is not needed for verification.

## The finish reply (`hgj/finish-summary/v1`)

```json
{"ok": true, "schema": "hgj/finish-summary/v1", "scoring_status": "scored",
 "score_summary": {"primary_score": {"points_earned": 18, "total_points": 18, "S_full": 1, "S_partial": 1.0},
                   "bolt_accuracy": {"correct": 60, "total": 60, "accuracy_percent": 100.0},
                   "checklist_accuracy": {"correct": 1647, "total": 1647, "accuracy_percent": 100.0},
                   "human_time": {"productive_seconds": 13630, "penalty_seconds": 0, "total_seconds": 13630, "reference_seconds": 13630},
                   "mistakes": {"count": 0, "by_type": {}}, "status": "scored", "tool_calls": 436},
 "record": {"file": "finish-record.json", "sha256": "...", "bytes": 5638747},
 "turns_remaining": 588}
```

(Values from the V1 correct scripted control; the checklist total depends on
the variant.)

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
