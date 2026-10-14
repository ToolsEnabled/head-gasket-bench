# Exploratory baseline run: `claude-haiku-5-5` (variant V1, standard job), run 3 of 3

A baseline run by ToolsEnabled with a low-cost model through a command-line client. It describes this run's behaviour; it does not rank models. The model label is the model the client requested; the serving system did not attest it.

## Harness

- Client: Claude Code 2.1.300, headless (`claude -p`), built-in tools disabled (`--tools ""`), only the 18 headgasket MCP tools allowed (permission mode `dontAsk`).
- The server ran through `tools/claude-code-proxy.py`, and Claude Code ran with `MAX_MCP_OUTPUT_TOKENS=150000`, so the result of `look` (about 200,000 characters) reached the model inline: the client saved 0 tool results to a file in this run.
- Prompt: the task prompt in `env/README.md`, verbatim.
- Environment: `env/` of release v0.1.0, variant V1, configuration `a4e22f01d85b…`, CPython 3.12.3.

## Result

| Quantity | Value |
|---|---|
| Points / 18 | 12 |
| S_partial | 0.333333 |
| S_full | 0 |
| Failed checkpoints | CP02, CP11, CP12 |
| Finished | yes |
| Tool attempts | 498 of 1,024 (391 ok, 107 refused) |
| Technician seconds, productive / penalty | 12,956 / 3,888 |
| Mistake events | 121 |
| Client-reported model turns, wall time, API-equivalent cost | 499, 828 s, $1.639 |

Independent scorer (`scorer/`): 12/18, primary checkpoints in agreement.
Technician seconds are analyst estimates, not measured labour. The client-reported figures come from the client at the end of the session, not from a provider receipt.

## What is published

The scored results (`environment-score.json`, `independent-score.json`) and `provenance.json`. The run's record and action journal are agent traces and are not published; their SHA-256 values are in `provenance.json`. Before they were withheld, the record passed `tools/validate_submission.py` (exact replay and the independent scorer).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
