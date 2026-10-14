# Security policy

ToolsEnabled's security policy applies to every ToolsEnabled product; this
file states it for the Head Gasket Bench environment. The full policy lives at
https://toolsenabled.ai/security/. The latest release is the supported one;
fixes ship as a new release.

## Report a problem

Please report a security problem privately, not in a public issue:

- use **Report a vulnerability** on this repository's **Security** tab
  (GitHub's private vulnerability reporting), or
- email **support@toolsenabled.ai**.

Tell us the environment version (`python3 -m headgasket --version`, and the
`source_manifest_sha256` that every run record carries), what you found, and
how to reproduce it. We read every report, reply as soon as we can, keep you
informed while we fix it, tell you when the fix is released, and credit you in
the release notes if you want that.

## What we ask

Good faith means: you test on computers, accounts and projects that are yours
or that you have permission to use; you stop once you can show the problem;
you do not access, change or keep other people's data beyond what you need to
show the problem; you do not disrupt services or other people; and you give us
a reasonable chance to fix the problem before you publish it. If we have not
fixed it within 90 days of your report, you may publish.

## Safe harbor

We will not treat good-faith research under this policy as an attack. We
consider it authorized, we will not bring or support legal action against you
for it, and we waive any part of our own terms that would otherwise stop it.
This covers ToolsEnabled's own code and releases; it cannot grant permission
for other parties' systems. Report a problem in an agent client, a model
provider or any other software we did not write to its own maker.

ToolsEnabled is a small, self-funded company and does not pay rewards for
reports.

## What this software does

The environment is a deterministic state machine written in Python 3.12
standard library only. It reads a configuration file and a pinned source
manifest, answers JSON-RPC requests on standard input and output, and writes
a run record into one folder you choose. It opens no sockets, reads no
environment secrets, executes nothing from the run folder, and loads no
third-party code.

`data/environment-source.json` lists the 18 runtime modules and the bootstrap
loader with their SHA-256 hashes. `tools/source_server.py` verifies the
manifest hash and every module hash and compiles the verified bytes before any
environment code runs; a changed file refuses to start. The same identity is
written into every run record, so a record can only replay against the exact
source that produced it. `python3 -m headgasket pins --check` repeats the
check.

Requests are bounded at 64 KiB per line, configurations at 16 MiB, run
records at 64 MiB, source files at 128 KiB, and the finish reply at 16 KiB
(summary) and 1 MiB (transport line). Oversized or malformed requests get a
JSON-RPC error and never reach the game state.

The server is not a sandbox for the AI client that drives it. It cannot stop a
client from using other tools, reading files or calling networks; isolating
the agent is the responsibility of the client and the person running it.
Verification of a submitted record proves that the recorded tool inputs
reproduce the recorded score under the pinned source; it does not prove which
model produced the inputs or how much time or money it spent.

Like every ToolsEnabled release, this software is provided "as is", without
warranty of any kind, as https://toolsenabled.ai/terms/ and the MIT licence
say.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
