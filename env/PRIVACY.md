# Privacy

Everything runs on your machine. The environment makes no network connection
of any kind: no telemetry, no update check, no model call, no upload.

What a run writes, all inside the one folder you name with `--out`. The
launcher makes sure that this folder is yours: it creates a new folder readable
only by you, and it refuses a folder that is a link or holds links, that belongs
to another user or that other users can write to. (The pinned server writes its
files by name, so someone else who could write to the folder could plant a link
there during the run and have the record written elsewhere. A folder your group
can write to is accepted; keep `--out` where only you can write.)

- `run.json`: the configuration, the actions your client sent, their results,
  the final state and the score.
- `actions.jsonl`: the same actions, one per line.
- `report.json`: counts, wall-clock seconds and copies of the score's parts,
  including the mistake events, which repeat the arguments of refused calls.
- `finish-record.json`: the complete record at the moment `finish` succeeded.
- `launch.json`: variant, pins, interpreter version and UTC start/end times.

A write that is interrupted can leave a temporary `*.tmp` copy of one of these
files. A start that makes no tool call records nothing and, when the server can
stop normally, leaves no files. When a client kills the server process itself
before it can clean up (a client that starts the server directly and then
signals it, or a kill of the whole process group), an empty `actions.jsonl` and
possibly a `run.json` and `report.json` with no actions are left; they hold no
tool arguments, and the next start in that folder clears them.

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
