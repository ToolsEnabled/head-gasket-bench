# Exploratory run: requested model `gpt-6-luna` (variant V1, standard job)

A single exploratory run. It describes this run's behaviour; it does not rank models and it is not a leaderboard entry. The requested model label is what the harness asked the provider for; the serving system did not attest which model or tier served the run. Model-call counts and API-equivalent prices were not available. Technician seconds are cited analyst estimates, not measured labour.

## Epoch

- Runtime commit `24a57135fc5d86e70e668880d8119556a40a9611` (amended epoch, Amendment 2), source manifest `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b`, environment-source identity `28a625063ff51e7a4464191088a17afe0ce012070b68f679fe98c3e201b41d0a`.
- Configuration V1: public pin `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` (sealed pin `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`; see `../../RECORDS.md`, section 5).
- Checkpoint rules: configuration label `amendment-1-20261009`; scored under Amendment 2 (`amendment-2-20261010`); independent scorer epoch `064d14a` (`amendment-2-20261010` selector, scorer source epoch `refit-preparation-20261010`).
- Harness: the provider's command-line coding agent, driven headlessly over its local JSON-RPC interface on the collection host and restricted to the environment's 18 MCP tools (no shell, file, browser or other tools); requested effort `xhigh`, requested service tier `default`; 1,024-attempt action budget, 4 h wall cap. Started 2026-10-10T03:53:24Z.

## Result, environment scorer and independent scorer side by side

| Quantity | Environment (`environment-score.json`) | Independent scorer, corrected epoch (`independent-score.json`, `corrected_epoch`) | Independent scorer, original seal (`independent-score.json`, `original_seal`) |
|---|---|---|---|
| Points / 18 | 13 | 13 | 13 |
| S_full | 0 | 0 | 0 |
| S_partial | 0.361111 | 0.361111 | 0.361111 |
| Failed checkpoints | CP02, CP05, CP12 | CP02, CP05, CP12 | CP02, CP05, CP12 |
| Productive s | 15,230 | 15,230 | 15,230 |
| Penalty s | 14,970 | 14,970 | 14,970 |
| Total s | 30,200 | 30,200 | 30,200 |
| Mistake events (distinct) and labels by type | 309 distinct: blocked_removal 7, invalid_action 110, missing_attachment_restore 1, redo_work 191, wrong_gasket 1 | labels: blocked_removal 7, invalid_action 110, missing_attachment_restore 1, redo_work 191, wrong_gasket 1 (an overlapping label shares one event) | labels: blocked_removal 7, invalid_action 110, missing_attachment_restore 1, redo_work 191 |
| Head-bolt criteria | 60 / 60 | 60 / 60 | 60 / 60 |
| Checklist (different item sets) | 1545 / 1647 | 1554 / 2759 (1204 unknown) | 1554 / 2759 (1204 unknown) |
| Tool attempts (ok / refused) | 807 (690 / 117) | 807 | 807 |
| Finished in the saved job | True | terminal reason `host_capture_limit_after_finish` | terminal reason `host_capture_limit_after_finish` |

Independent corrected-epoch note: one overlapping wrong_gasket label at attempt 747 added; no time or event-count change. The independent scorer's secondary checklist uses its own item set (2,759 items) and is not comparable with the environment's 1,647-item census; all shared values agree.

### Checkpoints

| ID | Weight | Checkpoint | Environment | Independent (corrected epoch) |
|---|---:|---|---|---|
| CP01 | 1 | Torque values, stages and sequence looked up before the first head-bolt tightening | pass | pass |
| CP02 | 2 | Disassembly in a valid order, with no attempt to remove a blocked part | FAIL | FAIL |
| CP03 | 1 | Cylinder 1 at TDC and timing marks aligned before the belt came off | pass | pass |
| CP04 | 1 | Head bolts loosened in the specified order and stages | pass | pass |
| CP05 | 1 | Head removed, old gasket removed, both surfaces cleaned | FAIL | FAIL |
| CP06 | 1 | Head and block flatness measured against the service limit, with the right decision | pass | pass |
| CP07 | 1 | Head bolts measured against the reuse limit, with the right decision | pass | pass |
| CP08 | 2 | Correct new gasket installed in the correct orientation on the dowels | pass | pass |
| CP09 | 2 | Stage-1 torque on all ten bolts, correct value and sequence | pass | pass |
| CP10 | 2 | Final torque on all ten bolts, correct value and sequence | pass | pass |
| CP11 | 2 | Timing restored: marks aligned, belt fitted and tensioned | pass | pass |
| CP12 | 2 | Reassembly complete: every removed part reinstalled with its fasteners | FAIL | FAIL |

## Resources

| Measurement | Value | Source |
|---|---|---|
| Agent wall time | unknown (host infrastructure stop; the setup-inclusive host session wall was 1,883.292 s) | host turn interval (study delivery index) |
| Environment session clock | 1881.524 s | the environment report's `real_time` (MCP server session monotonic clock; includes transport, excludes host setup) |
| Input tokens | 13,048,986 | host cumulative counters, PREFIX ONLY: latest cumulative counters observed before the capture stop; not terminal-turn totals |
| Output tokens | 62,622 (of which reasoning 47,946) | host cumulative counters, PREFIX ONLY: latest cumulative counters observed before the capture stop; not terminal-turn totals |
| Cache-read tokens (separate, not added to input) | 12,776,448 | host cumulative counters, PREFIX ONLY: latest cumulative counters observed before the capture stop; not terminal-turn totals |
| Model calls (Steps) | unknown | not exposed by the host event telemetry |
| API-equivalent cost | unknown | no cited rates applied |
| Head bolts correct | 50 / 50 registered (60 / 60 raw criteria) | environment score (registered = study's 5 derived criteria per bolt) |
| Host terminal state | host infrastructure stop (`durable_close`) while the `finish` reply was being returned; the model turn never became terminal | host collector |

Token counters keep the host convention: cache reads are reported separately and are not added to input a second time. The environment report records tokens as `not_recorded` because the environment never sees provider usage; the host counters above come from the harness.

## Known limits of this run

- Infrastructure stop at the finish reply: the environment accepted `finish` at action 807 and committed the scored final state, but the finish reply was a 1,602,630-byte JSON-RPC line that exceeded the collector's 1 MiB per-line capture bound. The host recorded an infrastructure stop (`durable_close`); the model turn never became terminal.
- Agent wall time is therefore unknown. The environment's own session clock (the environment report's `real_time`) is 1,881.524 s and the setup-inclusive host session wall was 1,883.292 s; neither is the agent-wall interval the other runs report.
- Token counters are a prefix: the latest cumulative counters observed before the capture stop, not terminal totals.
- The environment-scored final state at the finish action was accepted as the run's result by the coordinator's dated disposition (2026-10-10T04:35Z): "harness capture closed on the oversized finish response; model turn not terminal; job state final at the finish action". The original infrastructure-stop record is retained beside it. No fourth repair was run.
- Luna made 40 consecutive refused restoration requests (actions 424 to 463), removed the head and refitted the gasket without cleaning (692 to 693), and finished with 100 attachments still released (CP12).
- The hardened runtime epoch (aecadda) that fixes the oversized finish reply (compact `hgj/finish-summary/v1`, at most 956 bytes) postdates this run; no model run has used it.
- Served model and tier are unattested; the label is the request. No seed; the run is not reproducible as a model run, only as a record (replay).
- One run, one variant, no repeats: no interval, no comparison with the other runs.

## Files and hashes

**Agent traces stay private.** The per-action journal of this run (`run.json`, `actions.jsonl`), its per-action report (`report.json`) and the full independent-scorer results (which cite per-action evidence) are not published. This folder carries the scored results only: this file, the environment-scored summary and the independent-scored summaries. Before publication the public re-derived record was replayed byte for byte under the amended runtime with `env/` (`python3 -m headgasket replay`) and scored by `scorer/` with the same result as the sealed independent result; the hashes below identify the withheld files.

| File | SHA-256 | Bytes | Status |
|---|---|---:|---|
| `environment-score.json` | `a42e44da6f5df6840465841c7f1ecbaa092ec4e1bf7eb5af44fe4ce0efeea4b1` | 5,266 | published: report-level environment score |
| `independent-score.json` | `21e675334ebb128865026fb4dfd06251c64442bff9b4a647344ddbc3f7a24a3e` | 9,453 | published: report-level independent scores (corrected epoch and original seal) |
| `provenance.json` | (listed in `../../SHA256SUMS`) | | epoch pins, sealed-record hashes, verification lines |
| `run.json` | `297d4d877ad0ec33fc37eaaafc767706d4a976ed1df2cf1dd4b789bdd728d257` | 10,893,050 | not published |
| `actions.jsonl` | `dffa2cd6dcce5f64e755cf2ecaa81172b3953160abf0398753945f1fbb944022` | 6,157,909 | not published |
| `report.json` | `258102e5b3e3893f0c63b8a2a89beb0b3d0d3905521d8ab20bfcf077c09bbcd7` | 1,393,172 | not published |
| `independent-result.json` | `3341881f22757eab48b2d734268b2b1731372447e805fecac2ef3ca184bfe8aa` | 74,252 | not published |
| `independent-result-original-seal.json` | `dba07338998ce6c534a7faa69ffdd4247af347b5d7777bc9b45274bc7e2c13dc` | 74,156 | not published |

Sealed originals (retained privately by the publisher; the independent results name them):

- `run.json` `47aa83bd91c98ef080400e790ad72213b09caad4c6829abadb2ab0b706298fc3` (11,120,931 bytes), `actions.jsonl` `51d981b1e5aa55cc2b0c58400d40e9be9d3e9e2aa433a9302517a166f77dc517`, `report.json` `803dc85289c52aafa5b524350c43b96f7a1b1b754de25a0dc00cb1848d127bcc`, configuration `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`.
- Public and sealed records replay byte-identically under runtime `24a5713` with their respective configurations (RECORDS.md, sections 5 and 6).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
