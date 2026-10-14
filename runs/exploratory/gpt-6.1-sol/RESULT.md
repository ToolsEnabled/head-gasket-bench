# Exploratory run: requested model `gpt-6.1-sol` (variant V1, standard job)

A single exploratory run. It describes this run's behaviour; it does not rank models and it is not a leaderboard entry. The requested model label is what the harness asked the provider for; the serving system did not attest which model or tier served the run. Model-call counts and API-equivalent prices were not available. Technician seconds are cited analyst estimates, not measured labour.

## Epoch

- Runtime commit `24a57135fc5d86e70e668880d8119556a40a9611` (amended epoch, Amendment 2), source manifest `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b`, environment-source identity `28a625063ff51e7a4464191088a17afe0ce012070b68f679fe98c3e201b41d0a`.
- Configuration V1: public pin `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` (sealed pin `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`; see `../../RECORDS.md`, section 5).
- Checkpoint rules: configuration label `amendment-1-20261009`; scored under Amendment 2 (`amendment-2-20261010`); independent scorer epoch `064d14a` (`amendment-2-20261010` selector, scorer source epoch `refit-preparation-20261010`).
- Harness: the provider's command-line coding agent, driven headlessly over its local JSON-RPC interface on the collection host and restricted to the environment's 18 MCP tools (no shell, file, browser or other tools); requested effort `xhigh`, requested service tier `default`; 1,024-attempt action budget, 4 h wall cap. Started 2026-10-10T03:17:37Z.

## Result, environment scorer and independent scorer side by side

| Quantity | Environment (`environment-score.json`) | Independent scorer, corrected epoch (`independent-score.json`, `corrected_epoch`) | Independent scorer, original seal (`independent-score.json`, `original_seal`) |
|---|---|---|---|
| Points / 18 | 3 | 3 | 3 |
| S_full | 0 | 0 | 0 |
| S_partial | 0.083333 | 0.083333 | 0.083333 |
| Failed checkpoints | CP02, CP04, CP05, CP07, CP08, CP09, CP10, CP11, CP12 | CP02, CP04, CP05, CP07, CP08, CP09, CP10, CP11, CP12 | CP02, CP04, CP05, CP07, CP08, CP09, CP10, CP11, CP12 |
| Productive s | 13,280 | 13,280 | 13,310 |
| Penalty s | 12,012 | 12,012 | 11,952 |
| Total s | 25,292 | 25,292 | 25,262 |
| Mistake events (distinct) and labels by type | 245 distinct: blocked_removal 3, invalid_action 28, redo_work 213, wrong_gasket 2 | labels: blocked_removal 3, invalid_action 28, redo_work 213, wrong_gasket 2 (an overlapping label shares one event) | labels: blocked_removal 3, invalid_action 28, redo_work 213 |
| Head-bolt criteria | 0 / 60 | 0 / 60 | 0 / 60 |
| Checklist (different item sets) | 778 / 1647 | 787 / 2759 (1204 unknown) | 787 / 2759 (1234 unknown) |
| Tool attempts (ok / refused) | 663 (632 / 31) | 663 | 663 |
| Finished in the saved job | False | terminal reason `model_turn_ended_unfinished` | terminal reason `turn_ended_unfinished` |

Independent corrected-epoch note: two wrong_gasket labels at attempts 489 and 490 added; 30 absent-bolt preparation criteria change from unknown to failed. The independent scorer's secondary checklist uses its own item set (2,759 items) and is not comparable with the environment's 1,647-item census; all shared values agree.

### Checkpoints

| ID | Weight | Checkpoint | Environment | Independent (corrected epoch) |
|---|---:|---|---|---|
| CP01 | 1 | Torque values, stages and sequence looked up before the first head-bolt tightening | pass | pass |
| CP02 | 2 | Disassembly in a valid order, with no attempt to remove a blocked part | FAIL | FAIL |
| CP03 | 1 | Cylinder 1 at TDC and timing marks aligned before the belt came off | pass | pass |
| CP04 | 1 | Head bolts loosened in the specified order and stages | FAIL | FAIL |
| CP05 | 1 | Head removed, old gasket removed, both surfaces cleaned | FAIL | FAIL |
| CP06 | 1 | Head and block flatness measured against the service limit, with the right decision | pass | pass |
| CP07 | 1 | Head bolts measured against the reuse limit, with the right decision | FAIL | FAIL |
| CP08 | 2 | Correct new gasket installed in the correct orientation on the dowels | FAIL | FAIL |
| CP09 | 2 | Stage-1 torque on all ten bolts, correct value and sequence | FAIL | FAIL |
| CP10 | 2 | Final torque on all ten bolts, correct value and sequence | FAIL | FAIL |
| CP11 | 2 | Timing restored: marks aligned, belt fitted and tensioned | FAIL | FAIL |
| CP12 | 2 | Reassembly complete: every removed part reinstalled with its fasteners | FAIL | FAIL |

## Resources

| Measurement | Value | Source |
|---|---|---|
| Agent wall time | 1,079.566 s | host turn interval (study delivery index) |
| Environment session clock | 1067.200 s | the environment report's `real_time` (MCP server session monotonic clock; includes transport, excludes host setup) |
| Input tokens | 3,877,499 | host cumulative counters, complete (terminal turn totals) |
| Output tokens | 22,686 (of which reasoning 12,062) | host cumulative counters, complete (terminal turn totals) |
| Cache-read tokens (separate, not added to input) | 3,767,168 | host cumulative counters, complete (terminal turn totals) |
| Model calls (Steps) | unknown | not exposed by the host event telemetry |
| API-equivalent cost | unknown | no cited rates applied |
| Head bolts correct | 0 / 50 registered (0 / 60 raw criteria) | environment score (registered = study's 5 derived criteria per bolt) |
| Host terminal state | model turn ended without a `finish` call (the worker never saw `finish`) | host collector |

Token counters keep the host convention: cache reads are reported separately and are not added to input a second time. The environment report records tokens as `not_recorded` because the environment never sees provider usage; the host counters above come from the harness.

## Known limits of this run

- The worker never received `finish`: the model ended its turn with the head, bolts and the replacement gasket on the tray. The record is scored as it stands (`scoring_status` in_progress, report status incomplete, terminal reason `input_ended_without_finish`).
- Sol discarded the old gasket (action 276), installed its only new gasket from stock instead of through `replace` (327), later removed it again (660) and could not obtain another ("Replacement supplies unavailable" at 438 and 661).
- The original independent seal charged 13,310 + 11,952 = 25,262 s and carried no wrong_gasket label; the corrected scorer epoch reproduces the in-game 13,280 + 12,012 = 25,292 s. Both are kept.
- Served model and tier are unattested; the label is the request. No seed; the run is not reproducible as a model run, only as a record (replay).
- One run, one variant, no repeats: no interval, no comparison with the other runs.

## Files and hashes

**Agent traces stay private.** The per-action journal of this run (`run.json`, `actions.jsonl`), its per-action report (`report.json`) and the full independent-scorer results (which cite per-action evidence) are not published. This folder carries the scored results only: this file, the environment-scored summary and the independent-scored summaries. Before publication the public re-derived record was replayed byte for byte under the amended runtime with `env/` (`python3 -m headgasket replay`) and scored by `scorer/` with the same result as the sealed independent result; the hashes below identify the withheld files.

| File | SHA-256 | Bytes | Status |
|---|---|---:|---|
| `environment-score.json` | `fc00b347df800162f6d6b42725e5c844ea9495d6db1e86888d815c90499a8f2e` | 67,798 | published: report-level environment score |
| `independent-score.json` | `2c8e27ea01bc452ce6f83c1069b7ad1d0109f9a69b972b9c3386e8f23d5e15bc` | 76,326 | published: report-level independent scores (corrected epoch and original seal) |
| `provenance.json` | (listed in `../../SHA256SUMS`) | | epoch pins, sealed-record hashes, verification lines |
| `run.json` | `18c7137c1d0e8491188811f3d960d1fa8226e01ef4ada5102009bd88e8e60430` | 8,049,727 | not published |
| `actions.jsonl` | `6eb856d2031864d2c7611b2ac25ee9302d8dd00936d07b00aa1873b0ecf6d26d` | 3,486,587 | not published |
| `report.json` | `bc2545591ab821c05b86b4d030ba7fae6b7ab5ed2d76d23f87c93833bc7266c8` | 1,226,160 | not published |
| `independent-result.json` | `bcce8b2c7f560b19ae3d345c69dae9680dc42d59a7aefe93a5b3e09e4e092d5e` | 93,728 | not published |
| `independent-result-original-seal.json` | `ebe01183812a10d773bc053583ee30a84088acfdd6a3f155b07b267f0e6b3ca9` | 93,626 | not published |

Sealed originals (retained privately by the publisher; the independent results name them):

- `run.json` `68cafb058c150977ff3e21a91f034d03b385148cba99b54399c370e4ab789c7d` (8,176,024 bytes), `actions.jsonl` `270fdf4ef2304691442316db54c66206f0d8d393ae86943b5f9e40502d56b671`, `report.json` `27516a6f5a5d7db2a88bc95b87f979811bb671e68cc8797f5efaf2790d282bc4`, configuration `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`.
- Public and sealed records replay byte-identically under runtime `24a5713` with their respective configurations (RECORDS.md, sections 5 and 6).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
