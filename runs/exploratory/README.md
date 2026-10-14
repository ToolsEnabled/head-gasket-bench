# Exploratory model runs: scored results only

Three exploratory runs, one per requested model (GPT-6.1-Sol, GPT-6-Astra,
GPT-6-Luna), on the standard job (V1), collected by ToolsEnabled on
2026-10-10 under the amended runtime (`24a5713`). They are single runs: they
describe behaviour and do not rank models.

**The per-action journals are not published.** Agent traces stay private: each
folder carries the scored results only.

| File | What it is |
|---|---|
| `RESULT.md` | the result, the environment and independent scores side by side, the checkpoint table, resources and known limits |
| `environment-score.json` | report-level environment score: points, S_full, S_partial, the twelve checkpoints, head-bolt results by position, checklist totals, technician seconds, mistake labels by type, tool-call counts |
| `independent-score.json` | report-level independent scores of the sealed record: the corrected scorer epoch (the paper's numbers) and the original seal |
| `provenance.json` | epoch pins, the hashes of the withheld files and of the sealed originals, and the verification lines |

The numbers match the paper's Table 1 and Appendix F. Before publication each
public re-derived record was replayed byte for byte with `env/` and rescored by
`scorer/` with the same result as the sealed independent result; the hashes of
the withheld `run.json`, `actions.jsonl` and `report.json` are in each
`provenance.json` and `RESULT.md`.

## Low-cost baseline: `claude-haiku-5-5` (three runs, 2026-10-14)

`claude-haiku-5-5-r1` to `-r3` are three baseline runs by ToolsEnabled with a
low-cost model through Claude Code, headless, with its built-in tools disabled
so that only the 18 job tools were available, the task prompt from
`env/README.md`, and `MAX_MCP_OUTPUT_TOKENS=150000` so that the result of `look`
reached the model whole. All three scored 0/18 and ended their turn without
calling `finish`, after 69, 19 and 15 of the 1,024 allowed tool calls. They ran
on this release's `env/` (hardened runtime, the public V1 pin). Their folders
have the same four files; `independent-score.json` holds one current scorer
result instead of two epochs, and `provenance.json` records the client, its
settings and the client-reported turns, wall time and API-equivalent cost.
Before their journals were withheld, each record passed
`tools/validate_submission.py` (exact replay and the independent scorer).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
