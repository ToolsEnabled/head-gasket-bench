# Head Gasket Bench 0.1.2

Patch release. It fixes what an independent check of 0.1.1 found in the
submission path, the pull-request check and the launcher, corrects the
documentation, and replaces the 0.1.1 baseline. The pinned environment runtime
(`env/hgj/`, `env/tools/source_server.py`, the amended epoch), the five
configurations, the scorer's scoring modules, the published records and the
paper are unchanged, so every published record replays and scores exactly as
before (`python3 -m headgasket pins --check` and the scorer's `SHA256SUMS`).

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
- **Copies are refused.** A record that makes the same tool calls as a published
  scripted record or another submission, or that is a withheld ToolsEnabled
  record, fails the new `duplicate` check. ToolsEnabled still cannot tell a model
  run from a scripted run that differs by one call; every 18/18 submission is
  reviewed by hand.
- **Declarations are plain text.** Folder names and dates are matched whole (a
  trailing newline no longer passes), a date must be a real `YYYY-MM-DD` date, and
  the values shown in `RESULT.md` and on the board may not hold control or
  bidirectional-override characters or backticks.
- **The secret and path scan reads decoded JSON** (escapes such as `/` no
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
- **Every pull request that touches `runs/` or `leaderboard/` is checked**,
  including one that edits only `leaderboard/board.json`; the board is rebuilt
  from the pull request's `runs/` with main's `build_board.py`.

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
- **`serve` refuses a `--out` that is a link or holds links**, creates a new folder
  readable only by its owner, and writes `launch.json` (now `0600`) without
  following links.
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

| Agent | Model | Points / 18 | Failed checkpoints | Tool calls (refused) | Finished |
|---|---|---:|---|---:|---|
| Claude Code | claude-haiku-5-5 (run 1) | 14 | CP02, CP12 | 516 (83) | yes |
| Claude Code | claude-haiku-5-5 (run 2) | 12 | CP02, CP11, CP12 | 530 (81) | yes |
| Claude Code | claude-haiku-5-5 (run 3) | 12 | CP02, CP11, CP12 | 498 (107) | yes |

Single runs describe behaviour; they are not estimates of model performance.

## Documentation

Corrected: a refused attempt is charged its base seconds as penalty (it is not
free); replay needs the exact CPython version that made a record (3.12.3 for the
published ones); the model runs' scores cannot be replayed from this repository
(their journals are withheld); counts (six exploratory model runs, seven board
rows, 14 cited service entries); which runs used which runtime; what the prompt
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
and "simulated engine" in the scorer's checkpoint document.

## Known issues (they need a new environment epoch)

These sit in pinned code; fixing them changes the runtime or scorer identity and
needs new pins and new runs.

- **Calls after the budget.** The environment still records a call made after
  the 1,024-attempt budget is spent, and the scorer accepts at most 1,024
  attempts, so such a record cannot be scored or submitted. Stop when
  `turns_remaining` reaches 0.
- **CP02 on refused preparation or release attempts.** On a run that makes a
  refused `prepare_condition` or `release_attachment` attempt during disassembly,
  the independent scorer counts it as a blocked removal attempt and fails CP02,
  while the environment can pass CP02. The validator keeps primary checkpoints
  strict and refuses such a run. Found on a local test run after 0.1.1.
- **The scorer's printed comparison status** says `disagreement` whenever the two
  checklists' item sets differ, which they always do.
- **Each `look` result is stored twice** (in `run.json` and `actions.jsonl`), so
  about 150 `look` calls exceed the submission size limit; every call rewrites
  and syncs the whole record, so long runs get slower.
- **Invalid UTF-8 and links in the pinned server.** The pinned server decodes its
  input outside its per-request error handling and writes its temporary files by
  following links; the launcher works around both.
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
