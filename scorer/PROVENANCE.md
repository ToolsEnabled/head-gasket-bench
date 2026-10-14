# Provenance and changes

This tree is a clean-room export of the scorer from the benchmark's
development repository. Nothing in it phones home, and no development-machine
paths, account names or private service-manual content are included.

## Scoring modules: ten byte-identical to the sealed epoch, two revised

This is scorer revision `refit-preparation-20261010+cp02-20261014`: the sealed
epoch below with one change to checkpoint CP02, made on 2026-10-14 and described
in the next section. Ten of the twelve files of `job_accuracy/` are
byte-identical to the sealed scorer epoch; `removal.py` and `checkpoints.py`
carry the CP02 revision and are no longer the sealed files.

The sealed epoch is `refit-preparation-20261010` (sealed packet
`repair-corrected-scorer-epoch-v1`, inventory SHA256
`3348ff7070059e739198622621f9d334f17b2e2842913ee2e1b8deea9a20e5b3`, source
commit `2da8d20`) and to the later `repair-joint-supplement-receiving-v1`
packet (inventory `be3cae7ac81d31dc322bad503e7bf39589bfaf5becf8a51c79f8f4ff727c9324`,
source commit `6d8347c`), which pins the same twelve modules. The per-file
hashes are in `PINS.json`, with the sealed pins of the two revised modules
kept beside their new hashes. The development package's `README.md` (which
described development-only tools and the unshipped supplement) is replaced by
this tree's `README.md` and `docs/`.

Under this epoch the thirteen scripted jobs of the amended reference family
(sealed packet `repair-amended-family-v1`, inventory
`0e2cf291bb682f9fd08a1379d23135846ac5f111cf64ff527a7154d858768b1d`; delivery
inventory `e641845ad500a41546d9b9153f246c03122a44e6ffca4fab86e430977a2229da`)
score as listed in `docs/SCORING.md`; the family was re-received with this
tree's `hgj_scorer.py verify-family` and accepted, 13 of 13, with primary and
shared-field agreement (with the sealed modules; the revision below leaves every
family assessment byte for byte the same).

## Revision `cp02-20261014`: which refused attempts fail CP02

**Why.** The paper defines CP02 (Appendix C, Table 6): "Disassembly followed
the documented removal policy. Any refused removal attempt of a part that was
still blocked or still attached fails CP02, and is also counted as a mistake."
The environment implements this in `env/hgj/checkpoints.py` (`disassembly()`):
a refused `remove` counts only when the part it names is the installed current
body of a source position and the removal policy decides
`BLOCKED_BY_BENCHMARK_RULE`, `REMOVE_WITH_ASSEMBLY` or `RETAINED_FOR_JOB`, or the
policy allows a route and the part is a scored fastener (the refusal then means
that it is still threaded, or that another installed part is still in its way). A refused
`prepare_condition` or `release_attachment`, and a refused `remove` of a part
already removed, of an unknown part or of a part that is not the current body of
its position, do not count. The sealed scorer counted every refused `remove`,
`prepare_condition` and `release_attachment` attempt, so the two scorers could
decide CP02 differently. This was found on 2026-10-14: five finished runs scored
16 of 18 in the environment and 14 of 18 under the sealed scorer, and the
submission validator, which requires every primary checkpoint to agree, refused
them.

**What changed.** `removal.py` (`replay`) now marks a refused `remove` as
counted when the environment's rule above holds, decided from the scorer's own
replay of the removal policy (the part's current body and location, the
policy mode of its position, whether a route is open, and whether it is a
scored fastener); `disassembly_invalid_attempts` holds the executed invalid
transitions, as before, and those counted refusals, and nothing else.
`checkpoints.py` takes CP02's `no_refused_removal_attempt` from that list (as
before, it reads every refused `remove` when a record has no removal policy).
Like the environment, the scorer reads a refused call's part as the call named
it: a refusal that names a part by its stock label (a part fitted from supply)
is not resolved to the part and is not counted.

| Module | Sealed SHA-256 | Revised SHA-256 |
|---|---|---|
| `job_accuracy/removal.py` | `5717705677a44c4239e8eee88fd2eb2397f183c3be98f958c231d468fc115ffd` | `3cd93b2e26755d83a4764f9b0e7a817aa00b476f035d6e66cb85581d53bbfa4c` |
| `job_accuracy/checkpoints.py` | `d00072a59f50894f972b9d711f7e6eef38ab5ce760572a5d1d8f2e7a8758abb5` | `c91a2c4f28a05fcf54cc3320963434c560174194e84d1e739351db7dc4f6c310` |

**What did not change.** The twelve checkpoint definitions, their weights and
the selectable rule revisions (`checkpoint_contracts.py`; the default is still
`amendment-2-20261010`), the other ten modules, the record format, the
environment and its pinned runtime. The JSON output's `scorer_epoch` field
still names the base epoch, `refit-preparation-20261010`; `PINS.json`
(`scorer_revision`) names the revision, and `hgj_scorer.py score` and `compare`
print it (`scorer revision: ...`), a line the sealed front end did not print.

**Effect on the records.** Every record ToolsEnabled holds was rescored with the
sealed and the revised modules: the 13 family records and the scripted
reference (assessments byte for byte the same), the three GPT exploratory
records and the three `claude-haiku-5-5` baseline records (the same points,
checkpoints, primary comparison and shared fields; only CP02's evidence list is
shorter: it no longer lists refused preparation and release attempts, or
removals refused because the part name was unknown), and the 13 other
model runs ToolsEnabled made, none published as a record (six earlier
`claude-haiku-5-5` runs and seven `claude-opus-5-5` runs). Points changed for
five records only: the five finished
`claude-opus-5-5` runs, 14 to 16 of 18, now in agreement with the
environment's 16. On every record the refused calls the revised scorer counts
are exactly those the environment's CP02 evidence holds. No published result
changed. The published `independent-score.json` files of the GPT runs record the
sealed epoch's results and say so (`scorer_source_sha256`); they are unchanged.

**Tests.** The scorer's 167 tests pass unchanged. The repository's
`tests/test_cp02_agreement.py` replays the scripted V1 record through the pinned
environment with refused calls added (preparation, release, a blocked part, a
part that comes off with its assembly, a part retained for the job, an
already-removed part, an unknown part, a stock part, a threaded head bolt, a
re-fitted bolt still engaged) and checks that the environment and this scorer
count the same refused calls and decide CP02 alike; the sealed modules fail it.

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
