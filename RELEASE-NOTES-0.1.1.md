# Head Gasket Bench 0.1.1

Patch release, 2026-10-14. The environment, the scorer, the five configurations,
the published records and the paper are unchanged from 0.1.0.

## Fixes

- **Submitting a run that stopped early works.** The validator compared the
  independent scorer's "unknown" (for example on a part the run never touched)
  with the environment's "false" and refused every run that stopped before
  reassembly. An unknown is no longer compared; every primary checkpoint and
  every shared field the independent scorer can determine must still agree.
- **The pull-request check uses trusted code.** Submissions are validated with
  the main branch's validator, environment and scorer, never with code from the
  pull request, and a submission pull request may change only
  `runs/submitted/<name>/` and `leaderboard/board.json`.
- **Large tool results.** `look` returns about 196,000 characters. Claude Code
  cuts an MCP result above `MAX_MCP_OUTPUT_TOKENS` tokens (25,000 by default)
  and saves it to a file that an agent limited to the job tools cannot read.
  Start it with a higher limit, for example `MAX_MCP_OUTPUT_TOKENS=150000 claude`,
  and check any client's limit before a run.

## A low-cost baseline

Three runs of `claude-haiku-5-5` through Claude Code (headless, built-in tools
disabled, only the 18 job tools, the README task prompt,
`MAX_MCP_OUTPUT_TOKENS=150000`). Each scored 0/18 and ended its turn without
calling `finish`, after 69, 19 and 15 of the 1,024 allowed tool calls. The
client reported about $0.04 of API-equivalent cost for the three together.
Scored results only, as for the other exploratory runs; each record passed the
validator before its journal was withheld.

| Agent | Model | Points / 18 | Tool calls | Finished |
|---|---|---:|---:|---|
| Claude Code | claude-haiku-5-5 (run 1) | 0 | 69 | no |
| Claude Code | claude-haiku-5-5 (run 2) | 0 | 19 | no |
| Claude Code | claude-haiku-5-5 (run 3) | 0 | 15 | no |

Single runs describe behaviour; they are not estimates of model performance.

Release files: `head-gasket-bench-0.1.1.tar.gz` (the repository at the release
commit), `paper.pdf` (unchanged, v25), and `SHA256SUMS`.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
