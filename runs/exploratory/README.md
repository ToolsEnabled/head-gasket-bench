# Exploratory model runs: scored results only

Eleven exploratory model runs by ToolsEnabled on the standard job (V1): the
paper's three, one per requested model (GPT-6.1-Sol, GPT-6-Astra, GPT-6-Luna),
collected on 2026-10-10 under the amended runtime (`24a5713`), and, outside the
paper, three `claude-haiku-5-5` runs and five `claude-opus-5-5` runs through
Claude Code, collected on 2026-10-14 under the current runtime. They describe
behaviour and do not rank models. No run completed the job correctly; the best
scored 16 of 18 (each of the five `claude-opus-5-5` runs).

**The per-action journals are not published.** Agent traces stay private: each
folder carries the scored results only.

| File | What it is |
|---|---|
| `RESULT.md` | the result, the environment and independent scores side by side, the checkpoint table, resources and known limits |
| `environment-score.json` | report-level environment score: points, S_full, S_partial, the twelve checkpoints, head-bolt results by position, checklist totals, technician seconds, mistake labels by type, tool-call counts |
| `independent-score.json` | report-level independent scores of the sealed record: the corrected scorer epoch (the paper's numbers) and the original seal |
| `provenance.json` | epoch pins, the hashes of the withheld files and of the sealed originals, and the verification lines |

The three GPT runs were collected with the research collector's own task text,
which is not part of this repository. Their numbers match the paper's Table 1
and Appendix F. Before publication each public re-derived record was replayed
byte for byte with `env/` and rescored by `scorer/` with the same result as the
sealed independent result; the hashes of the withheld `run.json`,
`actions.jsonl` and `report.json` are in each `provenance.json` and `RESULT.md`.

## Low-cost baseline: `claude-haiku-5-5` (three runs, 2026-10-14)

`claude-haiku-5-5-proxy-r1` to `-r3` are three baseline runs by ToolsEnabled with
a low-cost model through Claude Code, headless, with its built-in tools disabled
so that only the 18 job tools were available, and the task prompt from
`env/README.md`. The server was started through `tools/claude-code-proxy.py` and
Claude Code ran with `MAX_MCP_OUTPUT_TOKENS=150000`, so the result of `look`
reached the model inline. All three finished, scoring 14, 12 and 12 of 18; none
passed CP02 (disassembly order) or CP12 (reassembly complete), and two missed
CP11 (timing restored). Their folders have the same four files as the runs
above; `independent-score.json` holds one current scorer result, and
`provenance.json` records the client, its settings and the client-reported
turns, wall time and API-equivalent cost. Before their journals were withheld,
each record passed `tools/validate_submission.py` (exact replay and the
independent scorer).

## `claude-opus-5-5` at effort max (five runs, 2026-10-14)

`claude-opus-5-5-max-proxy-o1` to `-o5` are five runs by ToolsEnabled of
`claude-opus-5-5` through Claude Code at effort `max` (`--effort max`), with the
baseline's harness: headless, built-in tools disabled, only the 18 job tools,
the task prompt from `env/README.md`, the server started through
`tools/claude-code-proxy.py` and `MAX_MCP_OUTPUT_TOKENS=150000`. They ran one
after another and ToolsEnabled stopped after the fifth. All five finished with 16
of 18 points (Success 0) after 371 to 393 tool calls, and each failed only CP12
(reassembly complete), in the same way: the agent removed the old head gasket and
fitted the new gasket from supply with `install`, instead of exchanging the old
gasket for it with `replace`. The environment therefore counted the gasket's
service position as not refitted and refused every `restore_attachment` call, so
none of the 100 attachments the agent had released was restored by `finish`; a
late `replace` was refused because the new gasket was already installed. Each
`RESULT.md` names the calls. The client reported an API-equivalent cost of $8.44
to $10.28 per run ($45.94 for the five). The folders have the same four files as
the baseline's. Before their journals were withheld, each record passed
`tools/validate_submission.py` with this release's scorer (revision
`refit-preparation-20261010+cp02-20261014`). The scorer of 0.1.1 gave them 14 of
18, because it also failed CP02 on refused preparation and release attempts,
which the environment and the paper's definition do not count
(`../../scorer/PROVENANCE.md`).

Three other `claude-opus-5-5` runs at effort max are not listed. Two ran before
the proxy existed: Claude Code saved `look`'s result to a file and showed the
model a 2 KB preview, so they measured the client, not the model (1 of 18 after
181 tool calls, and 0 of 18 when ToolsEnabled stopped the second after 84). A
third run through the proxy was stopped by ToolsEnabled before it finished and
left no record.

## Withdrawn `claude-haiku-5-5` runs

Release 0.1.1 listed three other `claude-haiku-5-5` runs here (0/18 each, after
69, 19 and 15 tool calls, with `MAX_MCP_OUTPUT_TOKENS=150000` but without the
proxy). They were withdrawn in 0.1.2: Claude Code had saved `look`'s result to a
file and shown the model a short preview, so those runs measured the client, not
the model. Three runs before those, with the client's default limit of 25,000
tokens, stopped after 16, 52 and 32 tool calls at 0/18 and were never listed, for
the same reason. None of these six is on the board.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
