# Head Gasket Bench

**Can an AI agent do a head gasket job?**

An agent connects to this environment over MCP and replaces the head gasket on
a real 1990s 1.6 L SOHC inline-four. It has to find the specifications in a
service-information corpus, set the engine to top dead centre, strip the belt,
cover and accessories in a valid order, loosen and lift the head in stages,
clean and measure the mating faces, decide what to do about bolts and a
possibly warped head, fit the right gasket, torque ten head bolts in two stages
in the right order, restore the timing, put every part back, and call
`finish`. Every tool call, refused ones included, goes into a hash-chained
record that replays bit for bit and is scored against twelve written
checkpoints worth 18 points.

Nothing physical is simulated. A perfect score means the recorded procedure
satisfied the written rules; it does not mean a real engine would run, and the
game is not instructions for repairing a real engine.

This is part two of the ToolsEnabled benchmarks. [Engine Bench](https://toolsenabled.ai/bench/)
(part one, code at [github.com/ToolsEnabled/engine-bench](https://github.com/ToolsEnabled/engine-bench))
asks an agent to build the engine; this benchmark uses the same engine model
and asks it to repair one.

## What is here

| Folder | What it is | Licence |
|---|---|---|
| [`env/`](env/) | The environment: an MCP stdio server with 18 tools, five variants (V1-V5), replay and verify. Python 3.12 standard library only, no network | MIT |
| [`scorer/`](scorer/) | The independent checkpoint scorer: re-derives the twelve checkpoints from a saved record without trusting the environment's score | MIT |
| [`runs/`](runs/) | The published records: the 13-case scripted family, the scripted V1 reference, and the scored results of eleven exploratory model runs: the paper's three GPT runs, a three-run `claude-haiku-5-5` baseline and five `claude-opus-5-5` runs ([RECORDS.md](runs/RECORDS.md)) | MIT (data) |
| [`paper/`](paper/) | The report: `paper.pdf` (64 pages), `paper.docx`, `paper.txt`, figures, the claim-to-data ledger | CC BY 4.0 |
| [`leaderboard/`](leaderboard/) | `board.json`, built from `runs/` by `tools/build_board.py` | MIT |
| [`tools/`](tools/) | `validate_submission.py`, `build_board.py`, `check_pr_scope.py` (the pull-request scope check), `claude-code-proxy.py`, `make_release.sh` | MIT |
| [`BENCHMARK-CARD.md`](BENCHMARK-CARD.md), [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | What the benchmark is and is not; how to replay, rescore and collect | CC BY 4.0 |

## Results so far

The paper's three exploratory runs on the standard job (V1), one per model,
plus the scripted reference (from the paper's Table 1):

| Agent | Model | Points / 18 | Score (S_partial) | Success (S_full) | Technician s (productive + penalty) | Mistake events |
|---|---|---:|---:|---:|---|---:|
| Scripted reference | none | 18 | 100% | 100% | 13,630 + 0 | 0 |
| Codex CLI | GPT-6-Astra | 15 | 41.7% | 0% | 16,190 + 1,404 | 30 |
| Codex CLI | GPT-6-Luna | 13 | 36.1% | 0% | 15,230 + 14,970 | 309 |
| Codex CLI | GPT-6.1-Sol | 3 | 8.3% | 0% | 13,280 + 12,012 | 245 |

In the paper's own words: "Table 1 reports one exploratory run per model on the
standard job (V1), with the scripted reference for comparison. No run achieved
full completion." "With one run per model, these figures describe individual
runs; they are not estimates of model performance." Served model identity was
not attested ("The model names identify the model; served model identity was
not attested."), model-call counts and API-equivalent cost were not available,
and technician seconds are analyst estimates, not measured labour. The agent
traces of these runs (their per-action journals) are not published; their
folders carry the scored results only.

Runs ToolsEnabled made for release 0.1.2, outside the paper, through Claude Code
(headless, with its own tools turned off so that the agent had only the 18 job
tools, the server started through `tools/claude-code-proxy.py`,
`MAX_MCP_OUTPUT_TOKENS=150000`, the task prompt in [env/README.md](env/README.md);
scored results only, in [runs/exploratory](runs/exploratory/README.md)):

| Agent | Model | Runs | Points / 18, each run | Success (S_full) | Failed checkpoints |
|---|---|---:|---|---:|---|
| Claude Code, effort max | claude-opus-5-5 | 5 | 16, 16, 16, 16, 16 | 0% | CP12 in each |
| Claude Code | claude-haiku-5-5 | 3 | 14, 12, 12 | 0% | CP02 and CP12 in each, CP11 in two |

No agent has completed the job correctly. The best agent result so far is 16 of
18 points, by `claude-opus-5-5` at effort max, in 5 of 5 finished runs; the
scripted correct job scores 18 of 18. All five lost CP12 (reassembly complete) in
the same way: the agent removed the old head gasket and fitted the new one from
supply with `install`, instead of exchanging the old gasket for it with
`replace`. The environment then counts the old gasket's service position as
never refitted and refuses `restore_attachment` ("selected service positions are
not installed"), so none of the 100 attachments the agent had released was
restored, and a late `replace` was refused because the new gasket was already in
place. The client reported an API-equivalent cost of $8.44 to $10.28 per run.
These runs describe behaviour; they are not estimates of model performance.

Not on the board: release 0.1.1 listed three 0/18 `claude-haiku-5-5` runs, and
three runs before those were never listed. In all six, Claude Code had kept most
of `look`'s result from the model, so they measured the client rather than the
model; the same happened to two early `claude-opus-5-5` runs (1 and 0 of 18). A
sixth `claude-opus-5-5` run through the proxy was stopped by ToolsEnabled before
it finished and left no record.

## Quick start

You need CPython 3.12 and nothing else: no pip install, no compiler, no
browser. Check `python3 --version`; if it is not 3.12.x, write `python3.12`
wherever this README says `python3` (`serve` refuses any other interpreter,
because a record made with one cannot be replayed or submitted). A record
replays exactly only under the CPython version that made it; the published
records were made with 3.12.3.

The commands below use three placeholders for absolute paths: `/ABS/REPO` is
your clone of this repository, `/ABS/RUNS` a folder for run records outside the
clone, and `/ABS/WORK` an empty folder outside the clone where the agent's client
runs.

```sh
git clone https://github.com/ToolsEnabled/head-gasket-bench /ABS/REPO
cd /ABS/REPO/env
python3 -m headgasket pins --check     # the pinned runtime files and the five configurations
python3 -m headgasket tools            # the 18 tools
```

**Connect an MCP client.** One server process is one run: pick a variant and a
new or empty folder for the record. Use absolute paths. A start that makes no
tool call (a client's health check such as `claude mcp list` or
`claude mcp get`, or a session you quit before the agent called a tool) records
nothing, so the folder stays free for the real session (if a client kills the
server before it can clean up, the next start clears what is left); once the
agent has made a call, the folder holds that run, and the next run needs a new
folder. `serve` refuses a `--out` that belongs to another user or that other users
can write to. These
are the environment README's snippets (examples of the wiring, not a
recommendation of any client or model):

Claude Code, in the empty folder `/ABS/WORK` outside the clone (`claude mcp add`
registers the server only for the folder it is run in, so run both commands
there; `--tools ""` turns Claude Code's own tools off, so the agent has only the
18 job tools):

```sh
mkdir -p /ABS/WORK && cd /ABS/WORK
claude mcp add headgasket -- python3 /ABS/REPO/tools/claude-code-proxy.py python3 /ABS/REPO/env/bin/headgasket-mcp serve --variant V1 --out /ABS/RUNS/v1-first-try
MAX_MCP_OUTPUT_TOKENS=150000 claude --tools "" --allowedTools mcp__headgasket
```

or in `/ABS/WORK/.mcp.json`:

```json
{
  "mcpServers": {
    "headgasket": {
      "command": "python3",
      "args": ["/ABS/REPO/tools/claude-code-proxy.py", "python3",
               "/ABS/REPO/env/bin/headgasket-mcp", "serve", "--variant", "V1",
               "--out", "/ABS/RUNS/v1-first-try"]
    }
  }
}
```

Codex CLI (`~/.codex/config.toml`)

```toml
[mcp_servers.headgasket]
command = "python3"
args = ["/ABS/REPO/env/bin/headgasket-mcp", "serve", "--variant", "V1",
        "--out", "/ABS/RUNS/v1-first-try"]
startup_timeout_sec = 60
tool_timeout_sec = 600
```

This file is global, so every Codex session starts this server: remove the entry,
or point `--out` at a new folder, after the run.

Any other stdio MCP client that speaks MCP protocol version `2025-11-25`: start
the same command and exchange one JSON-RPC object per line; see
[env/README.md](env/README.md).

**Large tool results.** `look` returns about 200,000 characters (every part on the engine). Claude
Code saves an MCP result to a file and shows the model only a short preview
when the result is larger than the size the tool declares, and it cuts results
above `MAX_MCP_OUTPUT_TOKENS` (25,000 tokens by default). An agent limited to
the job tools then never sees the part list. So for Claude Code, start the
server through `tools/claude-code-proxy.py` as shown above: it adds the size
declaration (`_meta` `anthropic/maxResultSizeChars`) to each tool and passes
every message through unchanged, and the environment still writes its own
record. Start Claude Code with `MAX_MCP_OUTPUT_TOKENS=150000`. Other clients may
cut long results too; check yours before a run.

**Keep the agent to the job tools.** This repository holds complete correct
solutions: the scripted records under `runs/` and the reference route inside each
configuration under `env/configs/`. An agent that can read files could copy them.
Start the client in `/ABS/WORK`, outside the clone, with its own file and shell
tools turned off, and say how you did it in `SUBMISSION.json` `notes`. The
`claude-haiku-5-5` baseline ran Claude Code headless with this command, under a
five-hour time limit (`headgasket.mcp.json` holds the `mcpServers` object shown
above):

```sh
cd /ABS/WORK
MAX_MCP_OUTPUT_TOKENS=150000 claude -p "<the task prompt>" --model claude-haiku-5-5 \
  --tools "" --mcp-config /ABS/WORK/headgasket.mcp.json --strict-mcp-config \
  --allowedTools mcp__headgasket --permission-mode dontAsk --setting-sources project \
  --output-format stream-json --verbose --no-session-persistence > session.jsonl
```

`--tools ""` leaves only the 18 job tools, `--strict-mcp-config` keeps every other
MCP server out, `--setting-sources project` keeps user-level settings and hooks
out, `--no-session-persistence` does not save the session, and the session's
messages go to `session.jsonl`.

**Run.** Give the agent the task prompt from [env/README.md](env/README.md#run-it-with-an-mcp-client)
(or your own, and record it) and let it work until it calls `finish` or the
1,024-attempt budget runs out. Every attempt counts, refused ones included, and
a refused attempt is charged its base technician seconds as penalty. When
`turns_remaining` reaches 0, stop calling tools: `serve` answers any further call
with the budget refusal and does not record it, so the record stops at 1,024
attempts. (The pinned server itself would record it, and the pinned independent
scorer cannot score a record of more than 1,024 attempts, a known issue of this
environment epoch.)

**Validate.** From `/ABS/REPO/env`:

```sh
python3 -m headgasket replay --record /ABS/RUNS/v1-first-try/run.json
python3 -m headgasket verify --run /ABS/RUNS/v1-first-try
cd ../scorer && python3 hgj_scorer.py score /ABS/RUNS/v1-first-try/run.json
```

The scorer's last line, `comparison of shared secondary fields (bolts, mistakes,
time)`, says `disagreement` on every record, the published 18/18 ones included,
because the two checklists have different item sets (`hgj_scorer.py compare`
prints their sizes). A field that differs is printed as a line directly under
it; an independent value of `None` means unknown, and a `mistakes/by_type` line
that differs only by `missing_timing_verification` shows a mistake type only the
independent scorer has: neither is a difference
([REPRODUCIBILITY.md](REPRODUCIBILITY.md)). The published records have no such
line.

**Submit.** From the repository root (`cd /ABS/REPO`), copy `run.json`,
`actions.jsonl` and `report.json` into `runs/submitted/<name>/`, add
`SUBMISSION.json` ([SUBMISSIONS.md](SUBMISSIONS.md) shows it), then:

```sh
python3 tools/validate_submission.py --write-result runs/submitted/<name>
python3 tools/validate_submission.py runs/submitted/<name>
python3 tools/build_board.py
```

and open a pull request that adds `runs/submitted/<name>/` and the rebuilt
`leaderboard/board.json`. [SUBMISSIONS.md](SUBMISSIONS.md) has the details.

## The board

[`leaderboard/board.json`](leaderboard/board.json) lists one row per run, as
recorded: model label, client, variant, points, S_partial, S_full, penalty and
productive seconds, date and source. Rows are sorted by variant, then
S_partial. The twelve rows there today are runs by ToolsEnabled (the scripted
reference and eleven model runs) and are marked `exploratory`; they describe
behaviour and do not rank models. Submitted rows
appear when a pull request passes validation, a maintainer has reviewed it by
hand and it is merged ([MAINTAINING.md](MAINTAINING.md)). ToolsEnabled checks
that a submitted record replays exactly and scores the same under the
independent scorer; it does not verify which model served the run.

## Release files

Each release on GitHub has `head-gasket-bench-<version>.tar.gz` (the repository
at the release commit), `paper.pdf` and `SHA256SUMS`. Download the three into one
folder and run `sha256sum -c SHA256SUMS` (on macOS, `shasum -a 256 -c SHA256SUMS`).

## Licences

- Code (`env/`, `scorer/`, `tools/`, the workflow) and the run data: MIT,
  Copyright (c) 2026 ToolsEnabled, Inc. ([LICENSE](LICENSE)).
- The report text and figures (`paper/`) and the benchmark card and
  reproducibility guide: CC BY 4.0 ([paper/LICENSE](paper/LICENSE)).
- Service-source material cited by the corpus and the report keeps its
  publishers' terms; nothing of it is redistributed here ([NOTICE](NOTICE),
  [env/THIRD-PARTY.md](env/THIRD-PARTY.md)).

Questions and corrections: open an issue, or write to support@toolsenabled.ai.
Security problems: see [SECURITY.md](SECURITY.md).

Citation: [CITATION.cff](CITATION.cff).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
