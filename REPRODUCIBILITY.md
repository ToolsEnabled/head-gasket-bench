# Reproducibility guide

ToolsEnabled, Inc. · October 2026

Replaying a saved record, rescoring it independently, checking the report's
numbers and collecting a new model run are separate operations. This
repository supports the first two for every published scripted record (the 13
family cases and the V1 reference), the third for the report's headline
numbers, and supplies the environment for the fourth. The model runs'
journals are withheld (only their scored results and the files' SHA-256 values
are published), so their scores cannot be replayed or rescored from this
repository. Everything below needs CPython 3.12 and the
standard library only. Questions and corrections: issues on
ToolsEnabled/head-gasket-bench, or support@toolsenabled.ai.

## Replay a published record

Every record under `runs/family/` and `runs/reference/` replays byte for byte
with the environment in `env/`. From `env/`:

```sh
python3 -m headgasket replay --record ../runs/family/V1-correct/run.json
python3 -m headgasket verify --run ../runs/family/V1-correct
```

`replay` rebuilds the game from the configuration embedded in the record,
re-applies every recorded action and compares the regenerated record with the
saved one byte for byte. `verify` also checks the hash chain, `actions.jsonl`
and `report.json`. Both print one JSON line and exit 0 only on an exact match.
The configuration must be one of the five pinned configurations in
`env/configs/PINS.json`; the published records embed exactly those bytes. The
runtime is selected by the source manifest the record names: the hardened
runtime (`aecadda`) for the family, the amended runtime (`24a5713`, in
`env/epochs/amended-v5/`) for the V1 reference. A record replays only under the
CPython version that made it; the published records were made with 3.12.3, so
replaying them needs exactly that version.

Replay proves that the recorded tool inputs reproduce the recorded score under
the pinned source. It does not prove which model made the calls, how long it
took or what it cost. Replays of one journal are repeatability checks, not new
independent procedures.

## Rescore a record independently

The scorer in `scorer/` re-derives the twelve checkpoints, the bolt criteria,
the typed mistakes and the technician-time charges from the record itself and
compares them with the score the environment embedded:

```sh
cd scorer
python3 hgj_scorer.py score ../runs/family/V1-correct/run.json
python3 hgj_scorer.py compare ../runs/family/V1-correct/run.json
```

Primary checkpoint outcomes and the shared bolt, mistake and time fields must
agree. The secondary checklists use different item sets (the environment's
1,647-1,674 items against the scorer's 2,759-2,799) and are never compared as
equal percentages; agreement on shared fields does not make every predicate
equal. Because the item sets differ, the scorer's line `comparison of shared
secondary fields (bolts, mistakes, time)` reads `disagreement` on every record,
the 18/18 ones included; `compare` lists the item-set sizes and, below them, any
field that really differs. For the published records no field differs.

## Regenerate the configurations and the scripted family

The five configurations are generated from `env/data/` and
`env/removal-policy/`, and the generator reproduces the pinned files byte for
byte:

```sh
cd env
python3 -m headgasket prepare --variant V1 --out V1.json && cmp V1.json configs/V1.configuration.json
python3 -m headgasket family --out NEW_FOLDER     # 13 serves + 26 replays, about an hour
```

## Check the report's numbers

`paper/claim-to-data.csv` binds every number printed in the report (905
claims) to the saved data it came from: the producing file, its SHA-256, the
packet inventory and a JSON pointer. The producers are the sealed research
packets, which are not part of this repository; their locators are written as
`sealed:<lane>/<packet>/<path>` (see `paper/README.md`). The headline numbers
can be checked directly against this repository: Table 1 and Appendix F against
`runs/reference/V1-amended/` and the three GPT runs' `runs/exploratory/gpt-*/environment-score.json`
and `independent-score.json` files, and the scripted family against
`runs/family/`. The report's own analysis toolchain (`tools.results_build` and
its audits) ran in the sealed research workspace and is not shipped.

## Original-rule references

The five primary original-rule scripts all earn 18/18 in the environment and
independent scorers. Actions are 450, 451, 452, 452 and 451; productive charges
are 14,050, 14,080, 15,310, 14,140 and 14,080 seconds for the standard,
stretched-bolt, machining, wrong-gasket and worn-belt variants. Penalties are
zero. These are analyst charges, not measured human times. A sixth correct
route replaces the head rather than machining it. These original-rule
references are reported in Appendix F of the report; they ran on an earlier
runtime (`95c3193`) under the original signed rules and are kept in the sealed
packets (environment delivery inventory
`72382f0f8d3bfd6c86f1a68739716aeb2998ab6cd035b7cceab91c7f0130fab6`,
independent comparison inventory
`78e7425330c929fed39d8c0f4077299c500450c741a42f0b8fdf85b97291dabc`), not in this
repository. The standard-job reference in Table 1 is the separate amended-rule
trace (18/18, 13,630 seconds), published in `runs/reference/V1-amended/`.

## Collect a new run

Serve a variant with `env/bin/headgasket-mcp serve --variant V? --out NEW_FOLDER`
under CPython 3.12 and connect a stdio MCP client (`env/README.md` has the
wiring and the task prompt). Run the client from an empty folder outside this
repository with only the job tools, because the repository holds complete correct
solutions, and stop when `turns_remaining` reaches 0 (a record of more than 1,024
attempts cannot be scored). Record the client and its version, the model identifier as the
provider reports it, the effort and service settings, the prompt, model calls,
input and output tokens, agent wall time, the termination, and dated API rates
if you want a cost. Steps means model calls, not tool attempts. Keep failed,
refused, incomplete and interrupted attempts; missing telemetry stays unknown.
Credentials and private account paths stay outside the run folder; the
environment records tool arguments exactly as the client sends them.

To have a run listed, submit it as described in `SUBMISSIONS.md`.

## Compare versions correctly

Amendments 1 and 2 govern current loosening and cover-gasket handling: choose
one complete documented loosening order and use it consistently across every
pass; a new head gasket is mandatory, and the valve-cover gasket may be new or
the original inspected and refitted with sealant. Records keep the rules and
runtime they were made with; historical records are never patched to claim new
behaviour. Keep scripted and model attempts in distinct groups. The report's
tables contain one exploratory run each for GPT-6.1-Sol, GPT-6-Astra and
GPT-6-Luna; these single runs describe behaviour and do not rank the models,
and confirmatory model comparison remains pending.

The report text and figures are CC BY 4.0; the benchmark code is MIT.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
