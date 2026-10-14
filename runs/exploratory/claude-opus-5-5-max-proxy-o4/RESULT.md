# Exploratory run: `claude-opus-5-5`, effort max (variant V1, standard job), run 4 of 5

An exploratory run by ToolsEnabled through a command-line client, one of 5 runs of the same model and setting. It describes this run's behaviour; it does not rank models. The model label is the model the client requested; the serving system did not attest it.

## Harness

- Client: Claude Code 2.1.300, headless (`claude -p`), effort `max` (`--effort max`), built-in tools disabled (`--tools ""`), only the 18 headgasket MCP tools allowed (permission mode `dontAsk`).
- The server ran through `tools/claude-code-proxy.py`, and Claude Code ran with `MAX_MCP_OUTPUT_TOKENS=150000`, so the result of `look` (about 200,000 characters) reached the model inline: the client saved 0 tool results to a file in this run.
- Prompt: the task prompt in `env/README.md`, verbatim.
- Environment: `env/` of release v0.1.0, variant V1, configuration `a4e22f01d85b…`, CPython 3.12.3.

## Result

| Quantity | Value |
|---|---|
| Points / 18 | 16 |
| S_partial | 0.444444 |
| S_full | 0 |
| Failed checkpoints | CP12 |
| Finished | yes |
| Tool attempts | 371 of 1,024 (365 ok, 6 refused) |
| Technician seconds, productive / penalty | 11,600 / 210 |
| Mistake events | 7 |
| Client-reported model turns, wall time, API-equivalent cost | 372, 701 s, $8.436 |

Independent scorer (`scorer/`): 16/18, primary checkpoints in agreement.
Technician seconds are analyst estimates, not measured labour. The client-reported figures come from the client at the end of the session, not from a provider receipt.

## Why CP12 failed

CP12 (reassembly complete) requirements not met: `part/gasket_old/replace`, `no_outstanding_attachments`. The agent removed the old head gasket (call 234) and fitted the new gasket from supply with `install` (call 261) instead of exchanging the old gasket for it with `replace`. The environment therefore counted the old gasket's service position as not refitted and refused all 4 `restore_attachment` calls the agent made ("selected service positions are not installed"), so none of the 100 attachments it had released was restored by `finish`. A `replace` of the old gasket at call 369 was refused because the new gasket was already installed. CP08 (correct new gasket, orientation, dowels) passed.

## What is published

The scored results (`environment-score.json`, `independent-score.json`) and `provenance.json`. The run's record and action journal are agent traces and are not published; their SHA-256 values are in `provenance.json`. Before they were withheld, the record passed `tools/validate_submission.py` (exact replay and the independent scorer).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
