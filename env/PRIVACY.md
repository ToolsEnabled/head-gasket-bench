# Privacy

Everything runs on your machine. The environment makes no network connection
of any kind: no telemetry, no update check, no model call, no upload.

What a run writes, all inside the one folder you name with `--out`:

- `run.json`: the configuration, the actions your client sent, their results,
  the final state and the score.
- `actions.jsonl`: the same actions, one per line.
- `report.json`: counts, wall-clock seconds and the score summary.
- `finish-record.json`: the complete record at the moment `finish` succeeded.
- `launch.json`: variant, pins, interpreter version and UTC start/end times.

Nothing in those files identifies you unless your client puts it into a tool
argument (tool arguments are recorded exactly). No usernames, home paths,
hostnames or environment variables are written. Token counts in `report.json`
are `null`; the environment has no way to know them.

ToolsEnabled receives nothing from a run. A record reaches ToolsEnabled only if
you open a pull request that contains it.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
