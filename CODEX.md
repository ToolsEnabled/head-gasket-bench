# Codex plugin

The local marketplace exposes Head Gasket Bench's eighteen stdio tools through
its source-bound launcher. This is a procedural benchmark game, not instructions
for real engine repair and not a ToolsEnabled Bench or Engine Bench package.
It is self-distributed; no OpenAI listing, endorsement or approval is claimed.

The Git marketplace requires CPython 3.12 on PATH as `python3`; the canonical CLI refuses a different
interpreter. Published records require 3.12.3 for byte-exact replay. Actual marketplace/client evidence covers Linux Codex 0.162.1; native Windows/macOS Codex integration is unverified.

The native Windows ZIP includes CPython 3.12.3 and derives its Codex manifest to
use `${PLUGIN_ROOT}/python/python.exe` directly. It never selects the machine's
Python 3.13 or a Windows Store alias. This one manifest derivation is recorded in
WINDOWS-MANIFEST.json with the original source digest; other source bytes remain
unchanged. For that route, verify and install the Windows ZIP first, then use
the local installation as the marketplace source:

```powershell
codex plugin marketplace add 'C:\your\installed-head-gasket-bench'
codex plugin add head-gasket-bench@head-gasket-bench-openai
$env:HEADGASKET_RUN_DIR = 'C:\your\new-private-record'
$env:HEADGASKET_VARIANT = 'V1'
```

Keep records outside the installation and plugin cache. The Git branch retains
its Linux interpreter entry; use the verified Windows distribution on Windows.
Native server execution and native Codex client/plugin acceptance are separate
gates; the latter still requires owner acceptance. The launcher uses the
[documented plugin-root placeholder](https://developers.openai.com/plugins/deploy/desktop-only).

The main-branch route below applies to the published 0.1.4 release; when deliberately
evaluating an unpublished candidate, select its exact reviewed `windows-port` ref.

```sh
codex plugin marketplace add ToolsEnabled/head-gasket-bench --ref main
codex plugin add head-gasket-bench@head-gasket-bench-openai
export HEADGASKET_RUN_DIR=/absolute/private/new-run
export HEADGASKET_VARIANT=V1
```

Start Codex from a separate empty work folder with those variables. The variant
defaults to V1; V1 through V5 are available. Use a fresh run folder outside the
installation for each session that calls a game tool. The launcher refuses
missing/relative/overlapping paths, then delegates interpreter, variant, owner,
privacy, exclusive-writer and unused-start recovery checks to the unchanged
canonical CLI. Symlink-resolved installation overlap is also refused. Health
checks without a tool call leave an unused folder available; a `look` call is a
real retained benchmark action. Do not delete a live lock or relabel a partial
run as finished. The package has explicit empty hooks and a separate Codex skill;
it does not load Claude lifecycle or pane code.

Only HEADGASKET_RUN_DIR and HEADGASKET_VARIANT are forwarded by this manifest.
There is no network connection, provider key, package installation or account in
the server. Codex can retain/send tool results to OpenAI under the user's own
login and terms. The run folder retains run.json, actions.jsonl and report.json,
including exactly the tool arguments supplied; inspect them before sharing.
Uninstalling the plugin does not delete records. Stop its server before deleting
or privately backing up the run folder. See [Privacy](env/PRIVACY.md),
[Security](env/SECURITY.md) and the MIT license. No applicable Head Gasket Bench terms URL has been established; the live
ToolsEnabled terms cover Fleet only, so Codex metadata deliberately omits that
link. Product terms and directory review remain lead-owned pending gates.
No submission or upload is performed by this package.
