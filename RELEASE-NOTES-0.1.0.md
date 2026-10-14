# Head Gasket Bench 0.1.0

First public release, 2026-10-14.

Can an AI agent do a head gasket job? An agent connects over MCP to an
environment with 18 tools and replaces the head gasket on a real 1990s 1.6 L
SOHC inline-four: look up the specifications, set the timing, take the engine
apart in a valid order, inspect and measure, choose parts, torque ten head
bolts in two stages in order, restore the timing, reassemble and finish. Every
call is recorded in a hash-chained record that replays bit for bit and is
scored against twelve checkpoints worth 18 points. Nothing physical is
simulated.

## What is included

- `env/`: the environment (MCP stdio server, five variants V1-V5, replay,
  verify, the configuration generator, the scripted-family driver), Python 3.12
  standard library only, no network. Its five configurations are
  byte-identical to the configurations in every published record.
- `scorer/`: the independent checkpoint scorer.
- `runs/`: the 13-case scripted family and the scripted V1 reference (full
  records), and the scored results of three exploratory model runs (their
  per-action agent traces are not published).
- `paper/`: the report, "Evaluating AI Agents on a Head-Gasket Repair
  Procedure" (64 pages; PDF, DOCX, text, figures, claim ledger).
- `tools/validate_submission.py`, `tools/build_board.py`,
  `leaderboard/board.json`, and the pull-request check for submissions.

Release files: `head-gasket-bench-0.1.0.tar.gz` (the repository at the
release commit), `paper.pdf`, and `SHA256SUMS`.

## Results

| Agent | Model | Points / 18 | Score | Success | Technician s (productive + penalty) |
|---|---|---:|---:|---:|---|
| Scripted reference | none | 18 | 100% | 100% | 13,630 + 0 |
| Codex CLI | GPT-6-Astra | 15 | 41.7% | 0% | 16,190 + 1,404 |
| Codex CLI | GPT-6-Luna | 13 | 36.1% | 0% | 15,230 + 14,970 |
| Codex CLI | GPT-6.1-Sol | 3 | 8.3% | 0% | 13,280 + 12,012 |

## Caveats

- One exploratory run per model, on the standard job only. In the report's
  words: "With one run per model, these figures describe individual runs; they
  are not estimates of model performance."
- No run achieved full completion.
- Served model identity was not attested; model-call counts and
  API-equivalent cost were not available.
- Technician seconds are analyst estimates, not measured labour.
- A perfect score means the recorded procedure satisfied the written rules,
  not that a real engine would run.

## How to submit

Run the environment with any MCP client, copy `run.json`, `actions.jsonl` and
`report.json` into `runs/submitted/<name>/`, add `SUBMISSION.json`, run
`python3 tools/validate_submission.py --write-result runs/submitted/<name>`
and `python3 tools/validate_submission.py runs/submitted/<name>`, and open a
pull request. See `SUBMISSIONS.md`.

Code and data: MIT. Report and figures: CC BY 4.0.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
