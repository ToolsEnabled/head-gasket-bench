# Provenance and changes

This tree is a clean-room export of the scorer from the benchmark's
development repository. Nothing in it phones home, and no development-machine
paths, account names or private service-manual content are included.

## Scoring modules: byte-identical to the sealed epoch

The twelve files of `job_accuracy/` are byte-identical to the sealed scorer
epoch `refit-preparation-20261010` (sealed packet
`repair-corrected-scorer-epoch-v1`, inventory SHA256
`3348ff7070059e739198622621f9d334f17b2e2842913ee2e1b8deea9a20e5b3`, source
commit `2da8d20`) and to the later `repair-joint-supplement-receiving-v1`
packet (inventory `be3cae7ac81d31dc322bad503e7bf39589bfaf5becf8a51c79f8f4ff727c9324`,
source commit `6d8347c`), which pins the same twelve modules. The per-file
hashes are in `PINS.json`. The development package's `README.md` (which
described development-only tools and the unshipped supplement) is replaced by
this tree's `README.md` and `docs/`.

Under this epoch the thirteen scripted jobs of the amended reference family
(sealed packet `repair-amended-family-v1`, inventory
`0e2cf291bb682f9fd08a1379d23135846ac5f111cf64ff527a7154d858768b1d`; delivery
inventory `e641845ad500a41546d9b9153f246c03122a44e6ffca4fab86e430977a2229da`)
score as listed in `docs/SCORING.md`; the family was re-received with this
tree's `hgj_scorer.py verify-family` and accepted, 13 of 13, with primary and
shared-field agreement.

## Tools

* `tools/receive_current_variants.py`: the family reader, unchanged except for
  one import. The development version imported a machine-wide resource floor
  (8 GiB free memory, 5 GB free disk, load average) from a physics-experiment
  tool that is not part of the scorer; it is replaced by a local function that
  only refuses to start when the output filesystem has under 256 MiB free. The
  receiving logic, bounds, gates and output format are unchanged.
* `tools/current_variant_source_roles.json` and
  `tools/test_repair_checkpoints.py`: byte-identical.
* `tools/relabel_citation_paths.py`: new. It rewrites machine-local citation
  paths inside a copy of a record and recommits the hashes that depend on the
  configuration. See the fixture note below.

## Tests

25 of the development repository's test files are shipped: every test of the
scorer. Left out: eight files that test the engine's CAD, timing and
rotating-assembly modules (not the scorer; they need cadquery, numpy and
mujoco), and the test of the unshipped joint-supplement receiver.

Two tests failed in the development repository at its final commit; both are
cases where the test's expected refusal name had drifted behind a deliberate
code change, which the lane's own close-out note records as "each expect an
older refusal name where a later check now refuses the same input first".
Both expectations are updated here:

1. `tests/test_current_transport.py`: the corruption that sets a call's
   `isError` flag to `0` was expected to be refused as
   `transport-call-values`. The compact-finish receiving change of
   2026-10-10 (development commit `ed6a962`) split the per-call check into an
   envelope gate (`transport-call-envelope`: request parameters, no error,
   `isError` is `False`, one text content item) and a value gate
   (`transport-call-values`). The test now expects `transport-call-envelope`
   for that corruption; the second corruption of the call value still expects
   `transport-call-values`.
2. `tests/test_successor_inputs.py`: the test appended a successful torque on
   a retained (non-serviced) fastener **after** the finish action and expected
   `unserviced-torque-success`. Since 2026-10-09 (development commit
   `f4c925a`, "Reject successful actions after a committed finish") the
   journal check refuses any successful action after a committed finish as
   `successful-action-after-finish`, before the torque is examined. The test
   now inserts the torque **before** the finish, re-links the state hashes and
   the final-state history, and still expects `unserviced-torque-success`,
   which is the behaviour it was written to prove.

Result: `python3 -m unittest discover -s tests` runs 167 tests, all passing.

## Fixtures

Four fixture folders under `evidence/job-accuracy/` hold the files the tests
read; only those files were copied (the folders' retained copies of old
scorer sources and result files were not). Their SHA256 values are in
`PINS.json`.

One fixture, `current-v1-reduction1/INPUT.json`, is a saved run whose
configuration cites the benchmark's design document by the absolute path it
had on the development machine (624 occurrences of one string leaf,
`config/benchmark_removal/reassembly/requirements[]/basis[]/sources[]/path`).
It is shipped relabelled with `tools/relabel_citation_paths.py`: the path is
replaced by the document's file name and the configuration hash, the state
identity hashes, the state hashes and the action chain are recommitted. The
only test that reads it (`test_variant_finish`) uses the configuration and the
final state, not the hashes. Scoring the original and the relabelled copy
gives identical results in every field except `config_sha256`,
`record_sha256` and `initial_evidence.initial_state_sha256`. The original
record's SHA256 and the relabelled one's are both in `PINS.json`. The
relabelled copy is no longer the sealed record.

## Not shipped

* `job_accuracy/joint_supplement.py`, `tools/receive_joint_supplement.py`,
  `tests/test_joint_supplement.py`: the receiver for the optional joint
  estimate, which is not part of scoring.
* The development repository's other tools (sealing, guards, physics probes,
  CAD builders), its evidence folders, its fleet reports and handoff notes.
* The reference family records themselves (289 MB); they are published with
  the environment, not with the scorer.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
