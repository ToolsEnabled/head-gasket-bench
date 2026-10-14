# Head Gasket Job scorer

The independent checkpoint scorer of the Head Gasket Job benchmark. It reads a
saved run record (schema `hgj/run/v2`: the configuration, the initial state,
every tool call with its result, and the final state) and decides the twelve
binary checkpoints of the benchmark, 18 points in all. It re-derives the
disassembly, installation and attachment history from the record itself; the
score the environment embedded in the record is used only for a comparison
afterwards. It does not run the environment, a model, an engine or a physical
simulation, and it never reads the network.

* `docs/CHECKPOINTS.md`: the twelve checkpoints in plain language, their
  weights, the two accepted loosening orders, how process and final-state
  checkpoints are judged, what the time charges are and are not, and the
  1,024-attempt budget.
* `docs/SCORING.md`: the formulas, the reference family's results, the
  secondary measures, and the note that the optional joint estimate is not
  part of scoring.
* `PROVENANCE.md`: where every file comes from and what was changed.
* `PINS.json`: the sealed hashes of the scoring modules and of the fixtures.

## Layout

```text
hgj_scorer.py             command-line front end (score, compare, verify-family)
job_accuracy/             the scorer package, pure Python 3.12+, standard library only
  checkpoints.py          the twelve checkpoints and the 18-point formula
  checkpoint_contracts.py the selectable rule revisions (signoff, amendment 1, amendment 2)
  independent.py          record validation, bolt criteria, mistakes, time charges
  removal.py              replay of the removal policy (disassembly / reassembly)
  refits.py               cover-gasket refit evidence
  finish.py               finish-time mistakes from final observations
  inputs.py               initial-state evidence and the attempt budget
  transport.py            byte-level joins of a saved delivery (records, journals, replays)
  usage.py                scripted-process usage receipts
  comparison.py           field-by-field comparison with the embedded score
  report.py               run report and professional summary
tools/
  receive_current_variants.py   reader for a complete thirteen-case family delivery
  current_variant_source_roles.json  the environment source files a delivery must pin
  test_repair_checkpoints.py    authored value tests of all twelve checkpoints
  relabel_citation_paths.py     rewrites machine-local citation paths in a record copy
tests/                    25 unittest files, 167 tests
evidence/job-accuracy/    the fixtures the tests read (four folders)
```

## Use

Score one saved run record under the current rule revision
(`amendment-2-20261010` is the default; `signoff-20261009` and
`amendment-1-20261009` reproduce earlier evaluations):

```sh
python3 hgj_scorer.py score path/to/run.json
python3 hgj_scorer.py score path/to/run.json --json report.json --markdown report.md
```

The output lists each checkpoint with its weight, PASS or FAIL and the
requirements not met, then points out of 18, S_full, S_partial, the
technician-time estimate (productive and penalty seconds, analyst estimates),
the typed mistakes, the tool-call counts, and the comparison with the score
the environment embedded in the record. A record the scorer cannot accept is
refused with a named reason and exit status 2 (for example `record-domain` for a
record of more than 1,024 attempts).

The last line, `comparison of shared secondary fields (bolts, mistakes, time)`,
reads `disagreement` whenever the two checklists have different item sets,
which they always do (the scorer has about 1,250 items the environment does not,
and the environment about 135 the scorer does not). The fields that differ are
listed under it (an independent value of `None` means unknown, not a
disagreement); `compare` also prints the item-set sizes. The published records
list none.

Show the comparison in detail (exit status 1 on a primary disagreement):

```sh
python3 hgj_scorer.py compare path/to/run.json
```

Receive a complete thirteen-case scripted family delivery, with the inventory
hash recorded outside the delivery and the retained environment source files:

```sh
python3 hgj_scorer.py verify-family --delivery DELIVERY_DIR \
    --inventory-sha256 HEX --source-root SOURCE_DIR --out NEW_DIR
```

The reader checks every pinned file, joins each record to its journal, its
two raw replays and its MCP request/response transcripts, assesses each case
twice, compares with the embedded scores and writes a per-case report and a
summary table to the output folder. Bounds: 512 delivery files, 16 MiB per
file, 1 GiB in all, 1,024 action attempts per record.

## Tests

```sh
python3 -m unittest discover -s tests
```

167 tests in 25 files; all pass. The tests use only the fixtures under
`evidence/job-accuracy/` and authored values; none runs the environment.

## What the scorer does not do

* It does not judge physics. Pass or fail follows procedure fidelity to a
  scripted reference and the benchmark's policy values (gasket stock, bolt
  stretch limit, flatness limit).
* Technician time is an analyst estimate per action, not a measurement.
* Agent wall time, tokens, model calls and cost come from separate receipts
  and stay unknown without them.
* The optional joint estimate (bolt preload and gasket contact) is not part of
  scoring and its receiver is not shipped here.

## Licence

MIT, ToolsEnabled, Inc. See `LICENSE`.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
