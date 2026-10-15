# Changelog

## 0.1.4

Native Windows NTFS run-folder ownership/ACL validation and lifetime writer and
ancestor handles; protected directory creation; deterministic self-contained
Windows ZIP and per-user offline PowerShell/cmd installation. Scientific pins
and scorer are unchanged. Qualification limits are in RELEASE-NOTES-0.1.4.md.

## 0.1.3

A launcher fix; details in `RELEASE-NOTES-0.1.3.md`. The pinned runtime (and so
the environment epoch), the configurations, the scorer, the published records,
the board and the paper are unchanged.

- Launcher (`env/headgasket/cli.py`, `serve`): a `remove` whose `route_id` is not
  one of the routes of an installed part that comes off on its own is answered by
  the launcher with the part's routes and does not reach the pinned server. The
  pinned environment refuses such a call, but then fails while it scores the
  refused call for CP02 and answers that call and every later one with a JSON-RPC
  error (`-32602`), so the run could not go on (a known issue in 0.1.2). The part
  is resolved as the game resolves it (its id or stock label, and a replacement
  fitted during the run); the internal id of a fitted replacement, which the game
  does not know but its scoring step reads as given, is answered too, after the
  pinned scoring step, run read-only, confirms that the call would stop it. The
  call is not recorded and uses no attempt, like a call after the budget (0.1.2);
  `serve` prints how many there were when it stops. Calls the environment refuses
  without stopping (an unknown part, no `route_id`, a part that is off or that
  comes off only with its assembly or stays for the job) reach it unchanged.
- `--version`, the start line and `launch.json` say 0.1.3.
- Tests: `env/tests/test_headgasket_cli.py` `RouteTests`: the refusal and the
  session after it; calls the environment refuses safely still reach it; the
  calls of `runs/family/V1-correct` with five such calls added produce that record
  byte for byte; every `remove` with a `route_id` in the 14 published records names
  one of its part's routes.
- Documentation: the known issue in `README.md`, `env/README.md`,
  `SUBMISSIONS.md` and `env/SECURITY.md`; `CITATION.cff` version.

## 0.1.2

Fixes from an independent check of 0.1.1, a scorer revision for CP02 and five
new board rows; details in `RELEASE-NOTES-0.1.2.md`. The pinned runtime, the
configurations, the published records and the paper are unchanged; two of the
scorer's twelve scoring modules are revised, and no published result changes.

- Scorer: revision `refit-preparation-20261010+cp02-20261014`. CP02 now counts
  refused attempts as the paper defines it (Appendix C) and as the environment
  decides it: a refused `remove` fails CP02 when the part is installed and the
  removal policy still blocks it, takes it off only with its assembly or keeps it
  for the job, or when it is a scored fastener whose route is open; a refused
  `prepare_condition` or `release_attachment`, or a `remove` refused for any other
  reason (a part already off, an unknown part, a stock label), no longer does.
  Before, the scorer failed CP02 on every refused `remove`,
  `prepare_condition` and `release_attachment` attempt while the environment did
  not, and the validator refused such a run. `job_accuracy/removal.py` and
  `job_accuracy/checkpoints.py` change (old and new SHA-256 in
  `scorer/PROVENANCE.md` and `scorer/PINS.json`); the checkpoint definitions
  (revision `amendment-2-20261010`) and the other ten modules are unchanged;
  `score` and `compare` print the revision. Every record ToolsEnabled holds was
  rescored with the old and the new modules: no published result changes, and the
  refused calls the new scorer counts equal the environment's CP02 evidence on
  every record. Tests: `tests/test_cp02_agreement.py` (records made by replaying
  the scripted V1 record through the pinned environment with refused calls
  added).
- Validator: a finished run without a final timing check, or one that calls
  `finish` early, is accepted (the independent-only mistake type
  `missing_timing_verification` is left out of the comparison; primary checkpoints
  stay strict). `RESULT.md` must equal the generated file; `report.json` must equal
  the environment's report for the record (only its wall-clock seconds are free);
  copies of published, withheld or submitted records are refused (`duplicate`),
  and a near copy (80% or more of the shorter record's calls, in order, shared with
  a scripted record or another submission) passes with `REVIEW BY HAND` on its
  `PASS` line; `RESULT.md` shows the calls in common with the closest scripted
  record, and the record's own technician seconds and mistake events (as on the
  board) instead of the independent scorer's; names and dates are matched whole
  and dates must be real; shown declaration values are plain text (no character of
  the Unicode control, format, separator, surrogate, private-use or unassigned
  categories, so U+061C and the zero-width marks are refused too); the secret and
  path scan reads decoded JSON and more formats; `--write-result` refuses a link;
  plain messages for empty, over-budget and oversized records. Tests: 38 (fresh
  fixtures instead of a copy of a published record).
- Pull-request check: `pull_request_target`, so the workflow and every script come
  from main and the pull request is read as data; it runs on every pull request
  (no paths filter); the scope check moved to `tools/check_pr_scope.py` and checks
  what merging would change (`git merge-tree`; more than one merge base or a
  conflict is refused), with git's NUL-separated output (names with spaces or
  newlines, links, nested folders, stray files and changes to existing
  submissions are refused) and at most ten submissions per pull request; a pull
  request that changes nothing under `runs/` or `leaderboard/` is a code change;
  the board is rebuilt from a submission pull request's runs with main's
  `build_board.py`, which refuses links, stray files and odd names under
  `runs/submitted/`; a `verdict` job sums up the others. The board test no longer
  breaks on the first accepted submission. `MAINTAINING.md` lists the GitHub
  settings the check needs and how a submission is reviewed. Tests: 27 scope and
  workflow tests, 3 new board tests.
- Launcher (`env/headgasket/cli.py`, not pinned): a start without any tool call
  records nothing and its leftovers are cleared; a lock keeps a second server out
  of a folder in use; `serve` refuses an interpreter other than CPython 3.12, a
  linked `--out`, links in it, and a `--out` of another user or that other users
  can write to; tool calls after the budget is spent are answered by the launcher
  and not recorded, so a record stops at 1,024 attempts; invalid UTF-8 input gets a
  JSON-RPC error; `launch.json` is written without following links, `0600`;
  version 0.1.2. Tests: 15.
- Claude Code: `tools/claude-code-proxy.py` passes `look`'s full result to the
  model; the READMEs show it and how to keep the agent to the 18 job tools.
- Board: the three 0.1.1 `claude-haiku-5-5` rows (0/18; Claude Code had kept most
  of `look`'s result from the model) are withdrawn and replaced by three runs
  through the proxy (14, 12 and 12 of 18). Five `claude-opus-5-5` runs (Claude
  Code, effort max, the same harness) are added: 16 of 18 each, CP12 failed in
  each (the new head gasket fitted with `install` instead of exchanged with
  `replace`, so no attachment could be restored). Two earlier `claude-opus-5-5`
  runs that hit the client limit, and one that ToolsEnabled stopped before it
  finished (no record), are not listed. Twelve rows in all.
- Documentation: refusals are charged penalty time; replay needs the exact CPython
  version; model-run scores cannot be replayed; counts and runtimes of the
  exploratory runs; the prompt; refusal hints; bench preparations; stdio clients;
  privacy statement; the `exploratory` flag; the scorer's `disagreement` line;
  `look` size and the 64 MB limit; the budget; placeholders; the board rebuild
  step; `SHA256SUMS`; one security address; the citation URL; the Claude Code
  snippet run in `/ABS/WORK`; the baseline's full command; the `compare` output;
  what a killed start leaves and when the record stays inside `--out`.
- Known issues that need a new environment epoch are listed in the release notes.

## 0.1.1 (2026-10-14)

- Validator: a run that stopped before reassembly can be submitted. The
  independent scorer reports some checklist items as unknown (for example on a
  part the run never touched); an unknown is no longer counted as a
  disagreement. Every determined shared field and every primary checkpoint must
  still agree. Found with a real early-stopping run; three unit tests.
- Pull-request check: submissions are validated with the base branch's
  validator, environment and scorer, never with code from the pull request; a
  submission pull request may change only `runs/submitted/<name>/` and
  `leaderboard/board.json`.
- Documentation: `look` returns about 196,000 characters, and Claude Code cuts
  MCP results above `MAX_MCP_OUTPUT_TOKENS` (25,000 tokens by default); both
  READMEs say to raise the limit and to check any client's limit.
- Board: a low-cost baseline, three runs of `claude-haiku-5-5` through Claude
  Code (0/18 each; scored results only).
- `env/`, `scorer/`, the configurations, the published records and the paper
  are unchanged.

## 0.1.0 (2026-10-14)

First public release.

- `env/`: the environment, an MCP stdio server with 18 tools and five
  variants; runtime `f347b0c8...` (hardened epoch `aecadda`) for new runs and
  the replay-only amended runtime `10967be0...` (epoch `24a5713`); V1-V5
  configurations byte-identical to the configurations in the published records.
- `scorer/`: the independent checkpoint scorer (scoring modules byte-identical
  to their sealed pins).
- `runs/`: the 13-case scripted family, the scripted V1 reference, and the
  scored results of three exploratory model runs (per-action agent traces not
  published).
- `paper/`: the report, v25 (64 pages), CC BY 4.0.
- `tools/validate_submission.py`, `tools/build_board.py`,
  `leaderboard/board.json`, the pull-request check, and the submission process.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
