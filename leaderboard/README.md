# Leaderboard data

`board.json` is built from the runs tree by `python3 tools/build_board.py`
(and checked with `--check` on every pull request that touches `runs/` or
`leaderboard/`). It is a JSON object with
`schema` (`head-gasket-bench/board/v1`), a `note`, the list of `fields`, and
`rows`, one per run, as recorded; nothing is averaged.

| Field | Meaning |
|---|---|
| `name` | `reference/<case>`, `exploratory/<run>` or `submitted/<name>` (the folder under `runs/`) |
| `model_label` | the model as stated (submissions) or as requested by the harness (exploratory runs); not an attested identity |
| `client` | the MCP client that drove the run, as stated |
| `variant` | V1-V5, from the record's configuration |
| `points` | checkpoint points out of 18 |
| `s_partial` | 0.5 × points / 18 + 0.5 × s_full, rounded to six decimals |
| `s_full` | 1 only if all twelve checkpoints pass |
| `penalty_s`, `productive_s` | charged technician seconds: analyst estimates, not measured labour |
| `date` | the run date (YYYY-MM-DD) |
| `source` | `run by ToolsEnabled`, or `submitted by <submitter>` |
| `exploratory` | `true` for the runs made by ToolsEnabled (the scripted reference and single model runs that describe behaviour and do not rank models); `false` for submissions |

Rows are sorted by variant, then `s_partial` (highest first), then `name`.
The same runs always give the same bytes.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
