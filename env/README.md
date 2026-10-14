# Head Gasket Job

An AI agent connects to this environment over MCP and replaces the head
gasket on a real 1990s 1.6 L SOHC inline-four. The engine is on a service
stand. The initial state reports the bench preparations (engine cold, battery
isolated, coolant drained, engine supported and others) as not yet done: the
agent records each with `prepare_condition`, and some removals need them. The
agent has to set the engine to top dead centre, strip the
belt, cover and accessories in a valid order, loosen and lift the head in
stages, clean and measure the mating faces, decide what to do about bolts and
a possibly warped head, fit the right gasket, torque the head in two stages in
the right order, restore the timing, put every part and attachment back, and
call `finish`.

Nothing physical is simulated. The environment is a deterministic procedure
game over 1,255 named engine bodies with 18 tools. Every well-formed tool
call, including a refused one, is journaled into a hash-chained record, and the record is
scored against twelve written checkpoints worth 18 points. A perfect score
means the recorded procedure satisfied the written rules; it does not mean a
real engine would run.

The environment is Python 3.12 standard library only. It makes no network
connection. It is one half of the ToolsEnabled Head Gasket Bench; this
directory is the part you run.

## Requirements

- CPython 3.12 (3.12.3 is the version the shipped records were made with;
  replaying them needs exactly that version). Check `python3 --version`; if it is
  not 3.12.x, write `python3.12` wherever this README says `python3`. `serve`
  refuses any other interpreter, because a record made with one cannot be
  replayed or submitted.
- Nothing else. No pip install, no compiler, no browser.

```sh
python3 -m headgasket pins --check     # verifies the 19 pinned source files and the 5 configurations
python3 -m headgasket tools            # prints the 18 tools
```

Run those from this directory (the one with `hgj/` in it), or use
`bin/headgasket-mcp`, which works from anywhere.

## The 18 tools

| Tool | What it does |
|---|---|
| `look` | View engine parts, named surface IDs and the job clock |
| `inspect` | Inspect an accessible component or surface (ID from `look`) |
| `measure` | Measure `flatness`, `bolt_stretch`, `bolt_free_length`, `roughness`, `gasket_bore` or `gasket_thickness` |
| `search_service_info` | Look up procedures, specifications and service diagrams (14 cited entries: the service entries E01-E12 and the benchmark-policy entries B01-B02) |
| `remove` | Withdraw an accessible, released part to the service tray |
| `install` | Fit one body from the tray or supply; timing phases in degrees |
| `clean` | Clean a face or prepare a removed fastener (`plastic_scraper`, `solvent`, `abrasive_disc`, `thread_brush`) |
| `replace` | Exchange a removed body for one distinct supply body |
| `torque` | One fastener operation: `tighten` with `value_N_m`, or `loosen` with a negative `angle_deg` |
| `check_timing` | Turn the crank 1-6 complete revolutions and inspect the timing marks |
| `parts_bin` | List available replacement stock and part markings |
| `machine_head` | Send the cleaned, removed head for the configured bench machining service |
| `set_timing` | Set crank and cam positions before disassembly |
| `tension_belt` | Complete the timing-belt tensioning operation |
| `prepare_condition` | Perform a named preparation step from the removal policy |
| `release_attachment` | Release a named attachment after its prerequisites are met |
| `restore_attachment` | Restore a released attachment after reassembly |
| `finish` | End the job and receive a compact score summary |

`python3 -m headgasket tools --json` prints the tool names, descriptions and
input schemas that the server publishes on `tools/list` (which also carries each
tool's annotations). Refusals name the argument or predicate that failed; some
also name a missing prerequisite step (for example "replace first" or "Start all
group fasteners before torque"). No refusal gives a torque value, the tightening
sequence or the correct stock part.

Budget: 1,024 tool-call attempts per run. Every attempt counts, refusals
included; a refusal rolls the state back, but its base technician seconds are
charged as penalty time. The reply to each call carries `turns_remaining`. When
it reaches 0, stop calling tools: the environment still records any further
call (and charges it), and the pinned independent scorer cannot score a record
of more than 1,024 attempts, so such a run cannot be submitted. That is a known
issue of this environment epoch.

## The five variants

| Variant | Starting condition | Configuration SHA-256 |
|---|---|---|
| V1 | Standard head-gasket replacement | `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` |
| V2 | One stretched head bolt (position 3, 0.2 mm) | `bf1726c9fa62f97d602f13c5d2483e9a59555632f5f37d493245e82d82ce679f` |
| V3 | Head exceeds the flatness limit (machine it or fit the replacement head) | `a210cc8d19ffbe4b3e8d84f375d2fe7ecfa53872b2386d16ba98680ce81d4b5d` |
| V4 | Incorrect gasket stock is also in the bin (78 mm / 1.2 mm beside the correct 75 mm / 0.762 mm MLS) | `797d52ba162e5c52dc36f954b9c6d57c237bd9377279983a6bd0480d462cb9fa` |
| V5 | Timing belt is worn (a new belt is in the bin) | `f7783d4e19f3cf9dccf2b28ad35d48c35ca4d6e39911913d709b26521baea998` |

Each configuration (`configs/V?.configuration.json`, about 2.9 MB) embeds the
geometry, the removal policy for the 1,255 bodies (1,240 source positions,
626 reinstallation requirements, 100 attachment restorations), the service
corpus, the labor table and the scored reference for that variant. The pins
are in `configs/PINS.json`; the server refuses a configuration whose hash
differs. These five files are byte-identical to the configurations embedded in
every published record under `../runs/`, and `python3 -m headgasket prepare`
regenerates each of them byte for byte from `data/` and `removal-policy/`.

## Run it with an MCP client

The server speaks MCP over stdio (newline-delimited JSON-RPC 2.0, protocol
version `2025-11-25`, server name `headgasket`); clients that only connect to
remote (HTTP) servers, or that need an older protocol version, cannot use it
directly. One server process is one run: pick a variant and a new or empty
folder for the record.

The snippets use three placeholders for absolute paths: `/ABS/REPO` is your clone
of the repository, `/ABS/RUNS` a folder for run records outside the clone, and
`/ABS/WORK` an empty folder outside the clone where the agent's client runs.

```sh
python3 /ABS/REPO/env/bin/headgasket-mcp serve --variant V1 --out /ABS/RUNS/v1-first-try
```

Use absolute paths; MCP clients start servers from a working directory you do
not control. The folder named by `--out` must be new or empty; `serve` creates
a new one readable only by you, refuses a folder that is a link or holds links,
and refuses a folder another `serve` is using. A start that makes no tool call
(a client's health check such as `claude mcp list` or `claude mcp get`, a
listed or restarted server, a session you quit before the agent called a tool)
records nothing and leaves nothing behind; if a client kills the server before
it can clean up, the next start clears those leftovers. Once the agent has made
a call, the folder holds that run, and the next run needs a new folder. The
server writes the record after every call, so an interrupted run keeps its
last committed state, and exits when the client closes its input. Each write
is synced to disk, so put `--out` on a local disk: a full run writes the
multi-megabyte record several hundred times, which is slow on network or
loop-mounted storage.

Configuration snippets for some clients follow. They are examples of the
wiring, not a recommendation of any client or model.

**Claude Code**

```sh
claude mcp add headgasket -- python3 /ABS/REPO/tools/claude-code-proxy.py python3 /ABS/REPO/env/bin/headgasket-mcp serve --variant V1 --out /ABS/RUNS/v1-first-try
MAX_MCP_OUTPUT_TOKENS=150000 claude
```

or in a project `.mcp.json`:

```json
{
  "mcpServers": {
    "headgasket": {
      "command": "python3",
      "args": ["/ABS/REPO/tools/claude-code-proxy.py", "python3",
               "/ABS/REPO/env/bin/headgasket-mcp", "serve", "--variant", "V1",
               "--out", "/ABS/RUNS/v1-first-try"]
    }
  }
}
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.headgasket]
command = "python3"
args = ["/ABS/REPO/env/bin/headgasket-mcp", "serve", "--variant", "V1",
        "--out", "/ABS/RUNS/v1-first-try"]
startup_timeout_sec = 60
tool_timeout_sec = 600
```

This file is global, so every Codex session starts this server: remove the
entry, or point `--out` at a new folder, after the run.

**Any other stdio MCP client**

Start the same command and exchange one JSON object per line on stdin and
stdout. The server answers `initialize`, `ping`, `tools/list` and `tools/call`,
accepts the `notifications/initialized` notification, and returns JSON-RPC
error `-32601` for other methods and `-32602` for malformed requests. The
minimal session:

```text
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"look","arguments":{}}}
```

Each `tools/call` reply is `{"content":[{"type":"text","text":"<JSON>"}],"isError":<bool>}`;
the text is the tool result, `ok` plus the observation or the refusal.
Requests are limited to 64 KiB per line.

**Large tool results**

`look` returns about 200,000 characters (every part on the engine). Claude
Code saves an MCP result to a file and shows the model only a short preview
when the result is larger than the size the tool declares, and it cuts results
above `MAX_MCP_OUTPUT_TOKENS` (25,000 tokens by default). An agent limited to
the job tools then never sees the part list. So for Claude Code, start the
server through `../tools/claude-code-proxy.py` as shown above: it adds the size
declaration (`_meta` `anthropic/maxResultSizeChars`) to each tool and passes
every message through unchanged, and the environment still writes its own
record. Start Claude Code with `MAX_MCP_OUTPUT_TOKENS=150000`. Other clients may
cut long results too; check yours before a run.

**Keep the agent to the job tools**

The repository holds complete correct solutions: the scripted records under
`../runs/` and the reference route inside each configuration in `configs/`. An
agent that can read files could copy them. Start the client in `/ABS/WORK`,
outside the clone, with its own file and shell tools turned off, and say how you
did it in `SUBMISSION.json` `notes`. The `claude-haiku-5-5` baseline ran Claude
Code like this (headless, only the 18 job tools; `headgasket.mcp.json` holds the
`mcpServers` object shown above):

```sh
cd /ABS/WORK
MAX_MCP_OUTPUT_TOKENS=150000 claude -p "<the task prompt>" --tools "" \
  --mcp-config /ABS/WORK/headgasket.mcp.json --strict-mcp-config \
  --allowedTools mcp__headgasket --permission-mode dontAsk
```

The server cannot enforce this: it is not a sandbox (see [SECURITY.md](SECURITY.md)).

**The task prompt**

The environment carries no prompt; the client supplies one. The scripted controls
need none (they send fixed tool calls), and the three GPT runs in the paper were
collected with the research collector's own task text, which is not part of this
repository. The `claude-haiku-5-5` baseline runs used this text verbatim, and you
can use it too:

> Replace the failed head gasket on the prepared service-stand engine and
> restore the assembly and timing. Use the headgasket tools to inspect, look
> up service information and do the work. End with finish within the work
> budget. Every job-tool call attempt, including a refused action, uses one
> environment turn. The remaining budget is shown in tool responses; if it is
> exhausted, end your response. Each successful action adds estimated
> technician time. Use only the supplied job tools.

Record the prompt you used with your run.

## What a run produces

All in the `--out` folder:

| File | Content |
|---|---|
| `run.json` | The record (`hgj/run/v2`): configuration, source identity, initial state, every action with its result and state hashes, final state, score |
| `actions.jsonl` | The action journal, one canonical JSON line per attempt |
| `report.json` | Usage envelope: wall-clock seconds, attempted/successful/refused counts, terminal reason, and copies of the score's parts: the time ledger, the mistake events (with the arguments of refused calls), bolt and checklist results |
| `finish-record.json` | The complete record at the moment `finish` succeeded (absent if the run never finished) |
| `launch.json` | Variant, configuration pin, source pin, interpreter version, UTC start and end (written when the server stops after at least one call) |

A start without any tool call leaves no files. The record is written atomically after every call. Each action row carries
`pre_state_sha256`, `post_state_sha256` and `previous_action_sha256`; the
chain starts at the configuration hash, so no action can be inserted, removed
or reordered without breaking it. See [docs/RECORD-FORMAT.md](docs/RECORD-FORMAT.md).

The reply the agent sees from `finish` is a compact summary
(`hgj/finish-summary/v1`, at most 16 KiB): points, pass/fail totals,
technician seconds, mistake counts, and the hash and byte count of the full
`finish-record.json`. The full scored record stays on disk.

Size: every `look` result (about 200,000 characters) is stored twice, in
`run.json` and in `actions.jsonl`, so each `look` call adds about 0.4 MB to the
folder. A run with about 150 or more `look` calls is larger than the 64 MB a
submission may be, and a `run.json` larger than 64 MiB (about 320 `look` calls)
cannot be replayed.

## Scoring

Twelve checkpoints, 18 points: `S_full` is 1 only when all twelve pass;
`S_partial = 0.5 × points / 18 + 0.5 × S_full`. Secondary measures are bolt
accuracy (60 items), checklist accuracy, typed mistakes and estimated
technician seconds (productive and penalty). The table and formulas are in
[docs/CHECKPOINTS.md](docs/CHECKPOINTS.md); the code is `hgj/checkpoints.py`
and `hgj/repair_scoring.py`. All durations are analyst estimates.

## Replay and verify

Any record replays bit for bit under the pinned source and the CPython version
that made it (3.12.3 for the published records):

```sh
python3 -m headgasket replay --record /ABS/RUNS/v1-first-try/run.json
python3 -m headgasket verify --run /ABS/RUNS/v1-first-try
```

`replay` rebuilds the game from the record's configuration, re-applies every
recorded action, and compares the regenerated record with the saved one byte
for byte (it also refuses a record whose configuration is not one of the five
pins unless you pass `--allow-unlisted-config`). `verify` additionally checks
the hash chain, `actions.jsonl`, `report.json` and, when present,
`finish-record.json` against the record (the published records omit that copy:
for a finished run it is the record itself). Both print one JSON line and exit
0 on success, 1 on any difference.

The runtime is chosen by the source manifest the record names. The current
runtime (`data/environment-source.json`, hardened epoch `aecadda`) serves new
runs and replays the scripted family. The earlier amended runtime (epoch
`24a5713`, `epochs/amended-v5/`, pinned in `configs/PINS.json` under `epochs`)
is replay-only: it made the published V1 reference run and the three GPT
exploratory runs of the paper (the `claude-haiku-5-5` baseline runs used the
current runtime). It differs from the current runtime in four modules
(`api`, `benchmark_geometry`, `game`, `mcp`: the compact finish reply and the
refusal wording); both use the same five configurations.

A record replays exactly only under the CPython version that made it (the
interpreter version is part of the recorded source identity). The published
records were made with CPython 3.12.3.

What verification proves: that the recorded tool inputs reproduce the recorded
score under this exact source. What it cannot prove: which model made the
calls, how long it really took, or what it cost.

## Scripted controls

`../runs/family/` holds the scripted family that `python3 -m headgasket family`
produces: six correct routes (V1-V5 and the V3 replacement-head route) and
seven faulty jobs, each served through the real stdio server. The correct
routes score 18/18; the faults lose the checkpoints they are built to lose. See
`../runs/RECORDS.md` for the table and hashes. No model was involved; these show
what the numbers mean.

## Submit a run

Submissions go to the repository root, not to this folder: see
`../SUBMISSIONS.md`. In short, copy `run.json`, `actions.jsonl` and
`report.json` from your `--out` folder into `runs/submitted/<name>/`, add
`SUBMISSION.json`, generate `RESULT.md` with
`python3 tools/validate_submission.py --write-result runs/submitted/<name>`,
check it with `python3 tools/validate_submission.py runs/submitted/<name>` and
open a pull request. `python3 -m headgasket validate <folder>` runs the
environment's part of those checks (finished run, pinned configuration, exact
replay) on its own. It refuses a run that did not call `finish`; the
repository's validator accepts such a run, and it is scored and listed as it
stands. Run the client outside the repository with only the job tools (above),
and stop when `turns_remaining` reaches 0.

Records contain exactly what your client sent as tool arguments. Look at the
file before you submit it.

## Regenerating the inputs

The five configurations are derived from `data/` and `removal-policy/` by the
shipped generator, so they can be rebuilt and compared with the pins:

```sh
python3 -m headgasket prepare --variant V1 --out V1.json && sha256sum V1.json configs/V1.configuration.json
python3 -m headgasket family --out /ABS/RUNS/new-family     # 13 serves + 26 replays, about an hour
```

## Tests

```sh
python3 -m unittest discover
```

The suite is standard-library `unittest`; it takes about a minute and runs no
model. Skipped tests are the Amendment 1 "pure helper" checks that
need a reference scorer that is not part of this release.

## Layout

```text
bin/headgasket-mcp     launcher (serve, replay, verify, validate, prepare, family, pins, tools)
headgasket/            the launcher's code; python3 -m headgasket is the same program
hgj/                   the runtime: 18 pinned modules + fixtures.py (software fixtures for tests)
tools/                 source_server.py (pinned loader), the configuration generator and the scripted-family driver
data/                  environment-source.json (the pin), service corpus, labor table, policy and retained bodies
removal-policy/        the L1 removal policy for the 1,255 bodies (input to the generator)
configs/               V1-V5 configurations and PINS.json
epochs/amended-v5/      the replay-only amended runtime (18 modules, bootstrap, manifest)
tests/                 unit tests
docs/                  CHECKPOINTS.md, RECORD-FORMAT.md, PROVENANCE.md
```

`python3 -m hgj.mcp` is the runtime module's own entry point and refuses to
start by design (it needs the source-bound loader); use the launcher.
[docs/PROVENANCE.md](docs/PROVENANCE.md) records exactly how this tree relates
to the sealed research epoch it came from and what was changed.

## Licence

Code and data in this directory: MIT, Copyright (c) 2026 ToolsEnabled, Inc.
([LICENSE](LICENSE)). Sources behind the service corpus are listed in
[THIRD-PARTY.md](THIRD-PARTY.md). See also [SECURITY.md](SECURITY.md) and
[PRIVACY.md](PRIVACY.md).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
Model and client names belong to their owners.
