# Head Gasket Bench 0.1.2

Patch release. It fixes what an independent check of 0.1.1 found in the
submission path, the pull-request check and the launcher, makes the independent
scorer decide CP02 as the paper defines it and the environment decides it,
corrects the documentation, replaces the 0.1.1 baseline and adds five
`claude-opus-5-5` runs to the board. The repository settings the check relies on
are in `MAINTAINING.md`. The pinned environment runtime (`env/hgj/`,
`env/tools/source_server.py`, the amended epoch), the five configurations, the
published records and the paper are unchanged, so every published record replays
exactly as before (`python3 -m headgasket pins --check`). Two of the scorer's
twelve scoring modules change (below); every published record gets the same
points, checkpoints and comparison as before (the scorer's `SHA256SUMS` lists the
new files).

## The scorer: CP02 as the paper defines it

The paper defines CP02 (Appendix C): "Disassembly followed the documented
removal policy. Any refused removal attempt of a part that was still blocked or
still attached fails CP02, and is also counted as a mistake." The environment
counts a refused `remove` only when the part it names is installed and the
removal policy still blocks it (`BLOCKED_BY_BENCHMARK_RULE`), takes it off only
with its assembly (`REMOVE_WITH_ASSEMBLY`) or keeps it for the job
(`RETAINED_FOR_JOB`), or when the part is a scored fastener (a head or cover
bolt) whose route is open, so that the refusal means it is still threaded or
another installed part is still in its way. The scorer of 0.1.0 and 0.1.1 failed
CP02 on every refused `remove`, `prepare_condition` and `release_attachment`
attempt, so a run with a refused preparation or release attempt, or a removal
refused because the part was already off, could pass CP02 in the environment and
fail it in the scorer, and the validator, which requires every primary checkpoint
to agree, refused it.
All five finished `claude-opus-5-5` runs below hit this (16 of 18 in the
environment, 14 under the old scorer).

- **Scorer revision `refit-preparation-20261010+cp02-20261014`.**
  `job_accuracy/removal.py` decides, from its own replay of the removal policy,
  which refused removals the environment's rule counts, and only those and
  executed invalid transitions fail CP02; `job_accuracy/checkpoints.py` reads
  CP02's refused removals from that list. Like the environment, the scorer reads
  a refused call's part as the call named it, so a refusal that names a part by
  its stock label is not counted. The checkpoint definitions, weights and rule
  revisions (`amendment-2-20261010` by default) and the other ten modules are
  unchanged. `scorer/PROVENANCE.md` now says that ten modules, not twelve, are
  the sealed files, names the two revised ones with their old and new SHA-256
  (also in `scorer/PINS.json`), and `score` and `compare` print the revision.
- **Rescored.** Every record ToolsEnabled holds was scored with the old and the
  new modules: the 13 family records and the reference (identical assessments),
  the three GPT records and the three `claude-haiku-5-5` baseline records (the
  same points, checkpoints, comparison and shared fields; only CP02's evidence
  list is shorter, without refused preparation and release attempts and removals
  of unknown part names), and 13 unpublished model runs. Points change only for
  the five `claude-opus-5-5` runs, 14 to 16, now in agreement with the
  environment. On
  every record the refused calls the new scorer counts are exactly those in the
  environment's CP02 evidence. No published result changes.
- **Tests.** `tests/test_cp02_agreement.py` replays the scripted V1 record
  through the pinned environment with refused calls added and checks, call by
  call, that the environment and the scorer count the same refusals: a refused
  `prepare_condition` or `release_attachment`, and a `remove` refused for a part
  already removed, an unknown part, a stock part or a stock label, count in
  neither; a `remove` of a part still blocked, of a part that comes off only with
  its assembly, of a part kept for the job, of a threaded head bolt, of the
  valve cover on threaded bolts, and of a refitted bolt still engaged count in
  both. The old scorer fails this test (it counts 11 refusals the environment
  does not). The scorer's 167 tests pass unchanged.

## Submissions

- **A finished run that skips the final timing check, or calls `finish` early, can
  be submitted.** The independent scorer has a mistake type the environment never
  produces (`missing_timing_verification`; the environment scores the same fact in
  checkpoint CP11, which both scorers decide and which must agree). The validator
  now compares the mistake types both scorers determine and leaves that one out;
  primary checkpoints stay strict. Before, such a run was refused, the commonest
  agent failures included.
- **`RESULT.md` must be exactly the file `--write-result` generates.** Before, any
  file holding the expected rows passed, so a forged table could be shown with the
  real rows hidden in a comment.
- **`report.json` must be exactly the report the environment writes for the
  record**; only its wall-clock seconds are free. Before, only five fields were
  checked, so a forged score, a token receipt or an extra key passed.
- **Copies are refused, near copies are marked.** A record that makes the same
  tool calls as a published scripted record or another submission, or that is a
  withheld ToolsEnabled record, fails the new `duplicate` check. A near copy (80%
  or more of the shorter record's calls, at least 20, are in order the calls of a
  scripted record or another submission; for example a scripted partial-credit
  record with one call added) passes, but its `PASS` line ends with
  `REVIEW BY HAND`, and every `RESULT.md` states how many calls the run shares
  with the closest scripted record. ToolsEnabled cannot tell an edited scripted
  run from a model run (the model runs it made share at most 52% of their calls
  with a scripted record); every submission, whatever its score, is reviewed by
  hand before it is merged (`MAINTAINING.md`). Repeated runs of one model can
  share most of their calls: any two of the five `claude-opus-5-5` runs share 282
  to 325 calls, in order (74% to 86% of the shorter run; three of the ten pairs
  reach the 80% mark), so a second submission of the same model may be marked for
  review; the mark asks for a look, not a refusal.
- **`RESULT.md` shows the same seconds and mistake events as the record and the
  board.** It showed the independent scorer's figures, which leave some values
  unknown (`penalty seconds | None` for a run that calls `finish` early) and count
  the independent-only `missing_timing_verification` mistake, so one submission
  showed two different penalty and mistake figures. Points and checkpoints, which
  both scorers decide and which must agree, are unchanged.
- **Declarations are plain text.** Folder names and dates are matched whole (a
  trailing newline no longer passes), a date must be a real `YYYY-MM-DD` date, and
  the values shown in `RESULT.md` and on the board may not hold control, format
  (every bidirectional mark, override and isolate, U+061C included, and the
  zero-width and byte-order marks), separator, private-use or unassigned
  characters, or backticks.
- **The secret and path scan reads decoded JSON** (escapes such as `\u002f` no
  longer hide a home path) and knows more formats: unquoted assignments, web
  tokens, more provider keys, non-ASCII user names, either path separator, WSL,
  `/media`, `/run/user` and lowercase `/users/` paths.
- **`--write-result` does not write through a link** in place of `RESULT.md`.
- **Plain messages** for a record with no tool call, a record of more than 1,024
  attempts (the pinned scorer cannot score it; see Known issues) and a folder over
  the size limit (each `look` call adds about 0.4 MB).

## The pull-request check

- **A pull request cannot change what its own check runs.** The workflow runs on
  `pull_request_target`, so GitHub takes it from the main branch; every script it
  runs comes from main, the pull request is read with git and checked out under
  `pr/` as data, nothing from it is executed, the token is read-only, no secrets
  are used and no checkout keeps credentials.
- **No submission skips validation.** The scope check (`tools/check_pr_scope.py`,
  tested) reads git's NUL-separated output, so a folder name with a space or a
  newline, a link, a nested folder or a stray file under `runs/submitted/` is
  refused instead of being dropped from the list; a pull request may only add new
  submission folders, so a change to or removal of an existing submission, or of a
  published record, goes to a maintainer. `tools/build_board.py` refuses links,
  stray files and odd names under `runs/submitted/` too.
- **The check compares main with the merge result.** It used the diff against
  one merge base, which a criss-cross history (a merge commit on main whose
  parents are not ancestors of each other, as GitHub's merge button makes for a
  pull request branched from an older main) could use to delete an accepted
  submission while the diff showed only a new folder. Now `git merge-tree` computes
  what merging would do and that is checked; a pull request with more than one
  merge base, or one that does not merge cleanly, is refused (rebase it).
- **Every pull request is checked**, with no paths filter (GitHub matches a
  filter against only the first 3,000 changed files, and a required check that a
  filter skips stays pending). A pull request that changes anything under `runs/`
  or `leaderboard/` is a submission pull request, including one that edits only
  `leaderboard/board.json`, and the board is rebuilt from its `runs/` with main's
  `build_board.py`; one that changes neither is a code change and passes to a
  maintainer's review. A new `verdict` job sums up the others (a skipped job
  counts as passed, so require `verdict` alone), and one pull request can add at
  most ten submissions.
- **The push-time tests no longer fail on the first accepted submission**: the
  board test checked that exactly the seven ToolsEnabled rows were listed.
- **The settings that make the check binding are written down** in
  `MAINTAINING.md`: a ruleset for main that requires review and the `verdict`
  check, squash-only merges, code owners, and what `pull_request_target` allows
  fork pull requests to start. Until they are set, the check only advises the
  maintainer.

## The launcher (`env/headgasket/`, not pinned)

- **A start without any tool call no longer uses up `--out`.** A client's health
  check (`claude mcp list`, `claude mcp get`), a listed or restarted server or a
  session quit before the first call records nothing and leaves nothing behind;
  if a client kills the server first, the next start clears the leftovers. A
  folder lock keeps a second server (such as a health check during a session) out
  of a folder in use.
- **`serve` refuses an interpreter other than CPython 3.12**, with a plain
  message, before any model time is spent. A record made with another interpreter
  could not be replayed or submitted.
- **`serve` refuses a `--out` that is a link or holds links, that belongs to
  another user or that other users can write to** (a folder writable by its
  group is accepted), creates a new folder readable only by its owner, and writes
  `launch.json` (now `0600`) without following links. Before, another local user
  could create `--out` in advance as an empty folder anyone can write to and plant
  a link in it after the start; the pinned server then overwrote the link's
  target with the record.
- **Calls after the budget are refused without being recorded.** Once the
  1,024-attempt budget is spent, `serve` answers any further tool call itself
  with the refusal the environment gives (`Environment turn budget reached`,
  `turns_remaining` 0) and does not pass it on, so the record stops at 1,024
  attempts and a full-budget run can be scored and submitted. Before, one more
  call (a `finish`, say) made a record of 1,025 attempts, which the pinned scorer
  cannot score.
- **Invalid UTF-8 on the input gets a JSON-RPC error** (`-32602`) and the session
  goes on; before, one such byte ended the run under a UTF-8 locale.
- **Version strings say 0.1.2** (`--version`, the start line, `launch.json`).
  The MCP `serverInfo` version and `env/configs/PINS.json` still say 0.1.0: they
  sit in pinned files.

## Claude Code and the baseline

- `look` returns about 200,000 characters. Claude Code saves an MCP result larger
  than the tool's declared result size to a file and shows the model a short
  preview, whatever `MAX_MCP_OUTPUT_TOKENS` says, so an agent limited to the job
  tools never saw the part list, and 0.1.1's advice (raise
  `MAX_MCP_OUTPUT_TOKENS`) did not help. `tools/claude-code-proxy.py` starts the
  environment unchanged and adds `_meta` `anthropic/maxResultSizeChars` to each
  tool in `tools/list`; every message is passed through unchanged. Both READMEs
  show it, and how to keep the agent to the 18 job tools.
- **The three 0.1.1 `claude-haiku-5-5` rows (0/18 each) are withdrawn.** They
  measured that client limit, not the model. Three runs before them, with the
  client's default limit, were never listed for the same reason.
- **The new baseline**: three runs of `claude-haiku-5-5` through Claude Code with
  the proxy (headless, only the 18 job tools, the task prompt in `env/README.md`)
  finished with 14, 12 and 12 of 18 points (Success 0). Each record passed the
  validator before its journal was withheld; scored results only, as for the other
  exploratory runs.
- **Five `claude-opus-5-5` runs at effort max are listed**, with the same harness
  (`--effort max`): all five finished with 16 of 18 points (Success 0), the highest
  agent score so far, and each failed only CP12 (reassembly complete), in the
  same way. The agent removed the old head gasket and fitted the new gasket from
  supply with `install`, instead of exchanging the old gasket for it with
  `replace`; the environment then counted the gasket's service position as not
  refitted and refused every `restore_attachment` ("selected service positions
  are not installed"), so none of the 100 attachments the agent had released was
  restored by `finish`, and a late `replace` was refused because the new gasket
  was already installed. The runs made 371 to 393 tool calls, and the client
  reported an API-equivalent cost of $8.44 to $10.28 per run ($45.94 for the
  five). Each record passed the validator with the revised scorer before its
  journal was withheld; under the 0.1.1 scorer they scored 14 and could not be
  submitted (see The scorer, above). No agent has completed the job correctly;
  the scripted correct job scores 18/18.
- **Three other `claude-opus-5-5` runs are not listed.** Two ran before the proxy
  existed and hit the same client limit: Claude Code saved `look`'s result to a
  file and showed the model a 2 KB preview (1 of 18 after 181 calls, and 0 of 18
  when ToolsEnabled stopped the second after 84). A sixth run through the proxy
  was stopped by ToolsEnabled before it finished and left no record.

| Agent | Model | Points / 18 | Failed checkpoints | Tool calls (refused) | Finished |
|---|---|---:|---|---:|---|
| Claude Code, effort max | claude-opus-5-5 (run 1) | 16 | CP12 | 392 (10) | yes |
| Claude Code, effort max | claude-opus-5-5 (run 2) | 16 | CP12 | 378 (10) | yes |
| Claude Code, effort max | claude-opus-5-5 (run 3) | 16 | CP12 | 393 (16) | yes |
| Claude Code, effort max | claude-opus-5-5 (run 4) | 16 | CP12 | 371 (6) | yes |
| Claude Code, effort max | claude-opus-5-5 (run 5) | 16 | CP12 | 383 (5) | yes |
| Claude Code | claude-haiku-5-5 (run 1) | 14 | CP02, CP12 | 516 (83) | yes |
| Claude Code | claude-haiku-5-5 (run 2) | 12 | CP02, CP11, CP12 | 530 (81) | yes |
| Claude Code | claude-haiku-5-5 (run 3) | 12 | CP02, CP11, CP12 | 498 (107) | yes |

Single runs describe behaviour; they are not estimates of model performance.

## Documentation

Corrected: a refused attempt is charged its base seconds as penalty (it is not
free); replay needs the exact CPython version that made a record (3.12.3 for the
published ones); the model runs' scores cannot be replayed from this repository
(their journals are withheld); counts (eleven exploratory model runs, twelve
board rows, 14 cited service entries); which runs used which runtime; what the prompt
was used for; what refusals say; the bench preparations the agent records with
`prepare_condition`; that the server needs a stdio MCP client; what `report.json`
and the privacy statement say about tool arguments; the `exploratory` flag; the
scorer's printed `disagreement` line (it comes from the two checklists' different
item sets; only listed fields are differences, and the published records have
none); the `look` size against the 64 MB submission limit; the budget (stop when
`turns_remaining` reaches 0); separate placeholders for the clone and the run
folders; rebuilding the board and returning to the repository root before
submitting; checking the release files with `SHA256SUMS`; one security address,
security@toolsenabled.ai; the citation URL, https://toolsenabled.ai/headgasket/;
"simulated engine" in the scorer's checkpoint document; the Claude Code snippet,
which now registers the server in `/ABS/WORK` (`claude mcp add` registers it for
the folder it is run in) and starts the client there with only the job tools; the
`claude-haiku-5-5` baseline's full command; where `compare` prints a differing
field and which values it does not compare (`None`, and the independent-only
`missing_timing_verification` mistake); and, in the privacy statement, what a
killed start can leave and when the record is written only into `--out`.

## Known issues (they need a new environment epoch)

These sit in pinned code; fixing them changes the runtime or scorer identity and
needs new pins and new runs.

- **Calls after the budget, in the pinned server.** The pinned server still
  records a call made after the 1,024-attempt budget is spent, and the scorer
  accepts at most 1,024 attempts. Through `serve` 0.1.2 such calls never reach
  the server (see The launcher); a record made with the 0.1.1 launcher, or with
  the pinned server started some other way, can still exceed the budget and
  cannot be scored or submitted.
- **A `remove` naming a route the part does not have stops the run.** For an
  installed part that comes off on its own, a `remove` whose `route_id` is not
  one of the part's routes is refused, but the pinned environment then fails
  while it scores CP02 (`unknown requested route`), and the server answers that
  call and every later one with a JSON-RPC error (`Invalid request`). The saved
  record keeps the calls made before it and can be scored and submitted as a run
  that stopped early. Found while testing the CP02 revision; leave `route_id`
  out, or name a route that `inspect` lists for the part.
- **The scorer's printed comparison status** says `disagreement` whenever the two
  checklists' item sets differ, which they always do.
- **Each `look` result is stored twice** (in `run.json` and `actions.jsonl`), so
  about 150 `look` calls exceed the submission size limit; every call rewrites
  and syncs the whole record, so long runs get slower.
- **Invalid UTF-8 and links in the pinned server.** The pinned server decodes its
  input outside its per-request error handling and writes its files by name,
  following links. The launcher works around both: it hands the server
  pre-decoded input, and it refuses a `--out` that holds links, is a link,
  belongs to another user or that other users can write to. A folder writable by
  a group you share with other users is accepted; keep `--out` where only you
  can write.
- **A killed start leaves files.** When a client kills the server process itself
  before it can clean up (a client that starts the server directly and then
  signals it, or a kill of the whole process group), the start leaves an empty
  `actions.jsonl` and possibly a record with no actions; the next start clears
  them, and they hold no tool arguments. Through `tools/claude-code-proxy.py`
  nothing is left.
- **The protocol version** is always `2025-11-25`, and parse errors are answered
  with `-32602` and a null id.
- **Service entry E01** says the engine is supplied cold, isolated, drained and
  supported, while the initial state reports those preparations as not done until
  the agent records them; the text is part of the pinned configurations.
- **Version strings** in `serverInfo` and `env/configs/PINS.json` say 0.1.0.
- The paper is unchanged; it says both benchmarks are published at
  https://toolsenabled.ai/bench/, where Head Gasket Bench has its own page at
  https://toolsenabled.ai/headgasket/.

## Release files

`head-gasket-bench-0.1.2.tar.gz` (the repository at the release commit),
`paper.pdf` (unchanged, v25) and `SHA256SUMS`. Download the three into one folder
and run `sha256sum -c SHA256SUMS` (on macOS, `shasum -a 256 -c SHA256SUMS`).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
