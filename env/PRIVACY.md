# Privacy

Everything runs on your machine. The environment makes no network connection
of any kind: no telemetry, no update check, no model call, no upload.

What a run writes, all inside the one folder you name with `--out`:

- `run.json`: the configuration, the actions your client sent, their results,
  the final state and the score.
- `actions.jsonl`: the same actions, one per line.
- `report.json`: counts, wall-clock seconds and copies of the score's parts,
  including the mistake events, which repeat the arguments of refused calls.
- `finish-record.json`: the complete record at the moment `finish` succeeded.
- `launch.json`: variant, pins, interpreter version and UTC start/end times.

A write that is interrupted can leave a temporary `*.tmp` copy of one of these
files. A start that makes no tool call leaves no files.

Tool arguments are recorded exactly as your client sends them, and they are
repeated in refusal messages, in the record's action history and in the mistake
events of `report.json`: if your client puts a user name, a home path, an e-mail
address or a host name into an argument, it is in those files. Apart from tool
arguments, the environment writes no usernames, home paths, hostnames or
environment variables (the `--out` path itself appears in no file). Token
counts in `report.json` are `null`; the environment has no way to know them.

ToolsEnabled receives nothing from a run. A record reaches ToolsEnabled only if
you open a pull request that contains it.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
