# Exploratory run: requested model `gpt-6-astra` (variant V1, standard job)

A single exploratory run. It describes this run's behaviour; it does not rank models and it is not a leaderboard entry. The requested model label is what the harness asked the provider for; the serving system did not attest which model or tier served the run. Model-call counts and API-equivalent prices were not available. Technician seconds are cited analyst estimates, not measured labour.

## Epoch

- Runtime commit `24a57135fc5d86e70e668880d8119556a40a9611` (amended epoch, Amendment 2), source manifest `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b`, environment-source identity `28a625063ff51e7a4464191088a17afe0ce012070b68f679fe98c3e201b41d0a`.
- Configuration V1: public pin `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` (sealed pin `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`; see `../../RECORDS.md`, section 5).
- Checkpoint rules: configuration label `amendment-1-20261009`; scored under Amendment 2 (`amendment-2-20261010`); independent scorer epoch `064d14a` (`amendment-2-20261010` selector, scorer source epoch `refit-preparation-20261010`).
- Harness: the provider's command-line coding agent, driven headlessly over its local JSON-RPC interface on the collection host and restricted to the environment's 18 MCP tools (no shell, file, browser or other tools); requested effort `xhigh`, requested service tier `default`; 1,024-attempt action budget, 4 h wall cap. Started 2026-10-10T03:40:30Z.

## Result, environment scorer and independent scorer side by side

| Quantity | Environment (`environment-score.json`) | Independent scorer, corrected epoch (`independent-score.json`, `corrected_epoch`) | Independent scorer, original seal (`independent-score.json`, `original_seal`) |
|---|---|---|---|
| Points / 18 | 15 | 15 | 15 |
| S_full | 0 | 0 | 0 |
| S_partial | 0.416667 | 0.416667 | 0.416667 |
| Failed checkpoints | CP02, CP04 | CP02, CP04 | CP02, CP04 |
| Productive s | 16,190 | 16,190 | 16,190 |
| Penalty s | 1,404 | 1,404 | 1,404 |
| Total s | 17,594 | 17,594 | 17,594 |
| Mistake events (distinct) and labels by type | 30 distinct: blocked_removal 1, invalid_action 14, redo_work 15 | labels: blocked_removal 1, invalid_action 14, redo_work 15 (an overlapping label shares one event) | labels: blocked_removal 1, invalid_action 14, redo_work 15 |
| Head-bolt criteria | 60 / 60 | 60 / 60 | 60 / 60 |
| Checklist (different item sets) | 1647 / 1647 | 1555 / 2759 (1204 unknown) | 1555 / 2759 (1204 unknown) |
| Tool attempts (ok / refused) | 528 (513 / 15) | 528 | 528 |
| Finished in the saved job | True | terminal reason `model_turn_completed` | terminal reason `turn_ended_after_finish` |

Independent corrected-epoch note: unchanged in every primary, bolt, mistake and labour value. The independent scorer's secondary checklist uses its own item set (2,759 items) and is not comparable with the environment's 1,647-item census; all shared values agree.

### Checkpoints

| ID | Weight | Checkpoint | Environment | Independent (corrected epoch) |
|---|---:|---|---|---|
| CP01 | 1 | Torque values, stages and sequence looked up before the first head-bolt tightening | pass | pass |
| CP02 | 2 | Disassembly in a valid order, with no attempt to remove a blocked part | FAIL | FAIL |
| CP03 | 1 | Cylinder 1 at TDC and timing marks aligned before the belt came off | pass | pass |
| CP04 | 1 | Head bolts loosened in the specified order and stages | FAIL | FAIL |
| CP05 | 1 | Head removed, old gasket removed, both surfaces cleaned | pass | pass |
| CP06 | 1 | Head and block flatness measured against the service limit, with the right decision | pass | pass |
| CP07 | 1 | Head bolts measured against the reuse limit, with the right decision | pass | pass |
| CP08 | 2 | Correct new gasket installed in the correct orientation on the dowels | pass | pass |
| CP09 | 2 | Stage-1 torque on all ten bolts, correct value and sequence | pass | pass |
| CP10 | 2 | Final torque on all ten bolts, correct value and sequence | pass | pass |
| CP11 | 2 | Timing restored: marks aligned, belt fitted and tensioned | pass | pass |
| CP12 | 2 | Reassembly complete: every removed part reinstalled with its fasteners | pass | pass |

## Resources

| Measurement | Value | Source |
|---|---|---|
| Agent wall time | 555.098 s | host turn interval (study delivery index) |
| Environment session clock | 534.960 s | the environment report's `real_time` (MCP server session monotonic clock; includes transport, excludes host setup) |
| Input tokens | 2,301,314 | host cumulative counters, complete (terminal turn totals) |
| Output tokens | 8,750 (of which reasoning 1,916) | host cumulative counters, complete (terminal turn totals) |
| Cache-read tokens (separate, not added to input) | 2,187,520 | host cumulative counters, complete (terminal turn totals) |
| Model calls (Steps) | unknown | not exposed by the host event telemetry |
| API-equivalent cost | unknown | no cited rates applied |
| Head bolts correct | 50 / 50 registered (60 / 60 raw criteria) | environment score (registered = study's 5 derived criteria per bolt) |
| Host terminal state | model turn completed after a successful `finish` | host collector |

Token counters keep the host convention: cache reads are reported separately and are not added to input a second time. The environment report records tokens as `not_recorded` because the environment never sees provider usage; the host counters above come from the harness.

## Known limits of this run

- CP02 failed for one refused removal: timing-cover screw 06 was attempted while the crank pulley still blocked it (action 113).
- CP04 failed because the first disassembly used four loosening passes (40 successful head-loosening commands) instead of the three-pass reference (30).
- Served model and tier are unattested; the label is the request. No seed; the run is not reproducible as a model run, only as a record (replay).
- One run, one variant, no repeats: no interval, no comparison with the other runs.

## Files and hashes

**Agent traces stay private.** The per-action journal of this run (`run.json`, `actions.jsonl`), its per-action report (`report.json`) and the full independent-scorer results (which cite per-action evidence) are not published. This folder carries the scored results only: this file, the environment-scored summary and the independent-scored summaries. Before publication the public re-derived record was replayed byte for byte under the amended runtime with `env/` (`python3 -m headgasket replay`) and scored by `scorer/` with the same result as the sealed independent result; the hashes below identify the withheld files.

| File | SHA-256 | Bytes | Status |
|---|---|---:|---|
| `environment-score.json` | `7204114a59441bd78b73295dd18aff619a924014162479da1c8bdc643c61a65a` | 4,835 | published: report-level environment score |
| `independent-score.json` | `785a9d5f0967a5988f2ec630e7c2ce88a022d7d3d9a4147f5bac7ce5464d3f53` | 9,076 | published: report-level independent scores (corrected epoch and original seal) |
| `provenance.json` | (listed in `../../SHA256SUMS`) | | epoch pins, sealed-record hashes, verification lines |
| `run.json` | `df2033e5eda8c5998094e8e2eaa9b3b70315068f5b382c6875e057c46c26b7cf` | 7,403,973 | not published |
| `actions.jsonl` | `18e3fbb49c6620f3bc09b1bec5b523818d9a0bab8db6568c2aec10d9db5418fd` | 3,359,669 | not published |
| `report.json` | `b3967b4816971fd9886aba930007913cc4de22160eda9af7a16722bdf2089379` | 748,466 | not published |
| `independent-result.json` | `51ff5d797a1f3accf92317e1da0a7a7aca5cbf45d418a9dc40dd24712a0f4f8f` | 65,759 | not published |
| `independent-result-original-seal.json` | `92ac2660579580effa8ab10a72b2feee6729f608a7054248b6a28403720fc611` | 65,683 | not published |

Sealed originals (retained privately by the publisher; the independent results name them):

- `run.json` `de05145dcd32de8cda6bf306a3f98881f8e4cc66a39d478071432362b7236b08` (7,553,910 bytes), `actions.jsonl` `52783657f02af55df40db67b508d44f341dba0b8cc0b4eba00acfa2e105c4532`, `report.json` `cce6607314986c26adc06b9a0df7f7c578c1be0f03cc8f7a208a7a119be9baaf`, configuration `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`.
- Public and sealed records replay byte-identically under runtime `24a5713` with their respective configurations (RECORDS.md, sections 5 and 6).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
