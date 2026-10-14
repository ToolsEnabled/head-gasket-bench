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
| [`runs/`](runs/) | The published records: the 13-case scripted family, the scripted V1 reference, and the scored results of three exploratory model runs ([RECORDS.md](runs/RECORDS.md)) | MIT (data) |
| [`paper/`](paper/) | The report: `paper.pdf` (64 pages), `paper.docx`, `paper.txt`, figures, the claim-to-data ledger | CC BY 4.0 |
| [`leaderboard/`](leaderboard/) | `board.json`, built from `runs/` by `tools/build_board.py` | MIT |
| [`tools/`](tools/) | `validate_submission.py`, `build_board.py`, `make_release.sh` | MIT |
| [`BENCHMARK-CARD.md`](BENCHMARK-CARD.md), [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | What the benchmark is and is not; how to replay, rescore and collect | CC BY 4.0 |

## Results so far

Three exploratory runs on the standard job (V1), one per model, plus the
scripted reference (from the paper's Table 1):

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

## Quick start

You need CPython 3.12 and nothing else: no pip install, no compiler, no
browser. A record replays exactly only under the CPython version that made it;
the published records were made with 3.12.3.

```sh
git clone https://github.com/ToolsEnabled/head-gasket-bench
cd head-gasket-bench/env
python3 -m headgasket pins --check     # the pinned runtime files and the five configurations
python3 -m headgasket tools            # the 18 tools
```

**Connect an MCP client.** One server process is one run: pick a variant and a
new folder for the record. Use absolute paths. These are the environment
README's snippets (examples of the wiring, not a recommendation of any client
or model):

Claude Code

```sh
claude mcp add headgasket -- python3 /ABS/PATH/env/bin/headgasket-mcp serve --variant V1 --out /ABS/PATH/runs/v1-first-try
```

or in a project `.mcp.json`:

```json
{
  "mcpServers": {
    "headgasket": {
      "command": "python3",
      "args": ["/ABS/PATH/env/bin/headgasket-mcp", "serve", "--variant", "V1",
               "--out", "/ABS/PATH/runs/v1-first-try"]
    }
  }
}
```

Codex CLI (`~/.codex/config.toml`)

```toml
[mcp_servers.headgasket]
command = "python3"
args = ["/ABS/PATH/env/bin/headgasket-mcp", "serve", "--variant", "V1",
        "--out", "/ABS/PATH/runs/v1-first-try"]
startup_timeout_sec = 60
tool_timeout_sec = 600
```

Any other stdio MCP client: start the same command and exchange one JSON-RPC
object per line (protocol version `2025-11-25`); see [env/README.md](env/README.md).

**Run.** Give the agent the task prompt from [env/README.md](env/README.md#run-it-with-an-mcp-client)
(or your own, and record it) and let it work until it calls `finish` or the
1,024-attempt budget runs out.

**Validate.** From `env/`:

```sh
python3 -m headgasket replay --record /ABS/PATH/runs/v1-first-try/run.json
python3 -m headgasket verify --run /ABS/PATH/runs/v1-first-try
cd ../scorer && python3 hgj_scorer.py score /ABS/PATH/runs/v1-first-try/run.json
```

**Submit.** Copy `run.json`, `actions.jsonl` and `report.json` into
`runs/submitted/<name>/`, add `SUBMISSION.json`, then:

```sh
python3 tools/validate_submission.py --write-result runs/submitted/<name>
python3 tools/validate_submission.py runs/submitted/<name>
```

and open a pull request. [SUBMISSIONS.md](SUBMISSIONS.md) has the details.

## The board

[`leaderboard/board.json`](leaderboard/board.json) lists one row per run, as
recorded: model label, client, variant, points, S_partial, S_full, penalty and
productive seconds, date and source. Rows are sorted by variant, then
S_partial. The four rows there today are runs by ToolsEnabled and are marked
`exploratory`; they describe behaviour and do not rank models. Submitted rows
appear when a pull request passes validation and is merged. ToolsEnabled checks
that a submitted record replays exactly and scores the same under the
independent scorer; it does not verify which model served the run.

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
