# Head Gasket Job benchmark: run records

This tree holds the public run records of the head-gasket replacement benchmark on a real 1990s 1.6 L SOHC inline-four engine: the sealed scripted family of the hardened environment epoch (13 cases), the three exploratory model runs, and the scripted reference the paper's Table 1 uses. Every record is a deterministic, hash-chained action journal that the environment runtime can replay bit for bit. The agent traces of the three model runs (their per-action journals) are not published: their folders carry the scored results only (`exploratory/README.md`). How to submit a run: `../SUBMISSIONS.md`.

**The three model runs are single exploratory runs, one per requested model, on the standard job only. They describe behaviour and do not rank the models.** No run completed the repair fully correctly (Success 0 for all three). There are no repeats, no intervals, no other variants, and the serving system did not attest the model identity. This is what the paper says, and it is the only reading these records support.

## 1. Layout

```
runs/
  RECORDS.md                      this file: format, epochs, replay, provenance
  SHA256SUMS                      every file below
  configurations/                 V1..V5 configurations (public pins) and the two source manifests
  family/<case>/                  13 sealed scripted cases, hardened runtime aecadda
    run.json actions.jsonl report.json RESULT.md provenance.json
  exploratory/<model>/            3 exploratory model runs, amended runtime 24a5713, variant V1: scored results only
  exploratory/claude-haiku-5-5-r*/ 3 low-cost baseline runs (2026-10-14), hardened runtime, variant V1: scored results only
    RESULT.md environment-score.json independent-score.json provenance.json
  reference/V1-amended/           the scripted 18/18 V1 reference of the amended epoch (13,630 s)
    run.json actions.jsonl report.json RESULT.md provenance.json
```

## 2. Record format (`hgj/run/v2`)

`run.json` is one canonical JSON document (keys sorted, separators `,` and `:`, UTF-8, no NaN, one trailing newline). Its top-level keys:

| Key | Content |
|---|---|
| `schema` | `hgj/run/v2` |
| `config`, `config_sha256` | the complete prepared configuration (variant, geometry, service corpus, labour table, mistake-time policy, removal policy, reviewed reference script, checkpoint revision) and its digest |
| `environment_source`, `environment_source_sha256` | the runtime closure identity: interpreter, the 18 `hgj` modules with their SHA-256, the bootstrap; and its digest |
| `initial_state`, `initial_state_sha256` | the prepared bench state and its digest; `initial_state.identity` carries the configuration and source digests |
| `actions` | the journal: one object per attempted tool call, refusals included |
| `budget` | `job-tool-action-attempts`: limit 1,024, used, exhausted |
| `final_state`, `final_state_sha256` | the committed state after the last action |
| `score`, `score_sha256`, `scoring_status`, `finished` | the environment's `hgj/repair-score/v1` (12 checkpoints, bolt and checklist accuracy, typed mistakes, charged technician seconds), `scored` or `in_progress`, whether a successful `finish` was committed |

Each action object has `seq`, `name`, `input`, `result` (`ok` true, or `ok` false with the refusal text), `human_time_charge` (base seconds, mistake assessments, citations), `pre_state_sha256`, `post_state_sha256` and `previous_action_sha256`.

**Hash chain.** `digest(x)` is SHA-256 over the canonical encoding of `x`. `actions[0].previous_action_sha256 == config_sha256`; for `i > 0`, `actions[i].previous_action_sha256 == digest(actions[i-1])`; `pre_state_sha256` and `post_state_sha256` are digests of the full state before and after the attempt, and each action's `pre_state_sha256` equals the previous action's `post_state_sha256` (a refusal leaves the mechanical state unchanged but is itself recorded in the state's action history, so the digest still advances); `score_sha256 == digest(score)`; `config_sha256 == digest(config)`. `actions.jsonl` is exactly the concatenation of `canonical(action)` for every entry of `actions`, one per line. `report.json` (`hgj/repair-run-report/v1`) is the usage envelope: `run_sha256` (SHA-256 of the `run.json` bytes), `score_sha256`, `real_time` (the environment's session clock), `tokens` (`not_recorded` unless a provider receipt was supplied), `tool_calls`, `terminal_reason`, and copies of the score's human-time ledger, mistakes, bolt and checklist accuracy and `primary_score`.

**Scoring.** Twelve binary checkpoints with weights 1, 2, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2 (18 points). `S_full = 1` only if all twelve pass; `S_partial = 0.5 * points / 18 + 0.5 * S_full`. Every attempted action, refusals included, is charged estimated technician seconds; successful correct work is productive, executed wrong work and refused attempts are penalty. The durations are cited analyst estimates, not measured labour.

## 3. How to replay and verify

Replay re-derives everything from the record and refuses any difference. It needs CPython 3.12.3 (the version the records were made with; the interpreter version is part of the recorded source identity) and the standard library only. From the repository's `env/` folder:

```
python3 -m headgasket replay --record ../runs/family/V1-correct/run.json
python3 -m headgasket verify --run ../runs/family/V1-correct
python3 -m headgasket replay --record ../runs/reference/V1-amended/run.json
```

`replay` checks that the embedded configuration is one of the five pinned configurations (`env/configs/PINS.json`; the files in `configurations/` here are byte-identical to them), selects the runtime the record names (the hardened runtime for `family/`, the replay-only amended runtime in `env/epochs/amended-v5/` for `reference/`), verifies that the record's `environment_source` identity equals the active closure, replays every action and compares each re-derived action object, the final state, the score and the complete record. `verify` adds the hash chain, `actions.jsonl` and `report.json`. Both print one JSON line and exit 0 only on an exact match. Independent of the runtime, anyone can check the hash chain with the rule in section 2 (`../tools/validate_submission.py` implements it with the standard library), and `../scorer/hgj_scorer.py score <run.json>` rescores a record without the environment.

## 4. Epochs

| Set | Runtime commit | Source manifest | Configuration (public pin) | Checkpoint revision | Independent scorer |
|---|---|---|---|---|---|
| `family/` (13 cases) | `aecadda60f795293c18d24d04ac91fe66b0a2278` (hardened v6) | `f347b0c8eee94ba36cd69818603178eb7e4c10e5afc4e21cf8eb8ec6308a4963` | V1 `a4e22f01d85b799e…`, V2 `bf1726c9fa62f97d…`, V3 `a210cc8d19ffbe4b…`, V4 `797d52ba162e5c52…`, V5 `f7783d4e19f3cf9d…` (full pins in `configurations/CONFIGURATIONS.md`) | configuration label `amendment-1-20261009`; scored under Amendment 2 (`amendment-2-20261010`) | family comparison at scorer commit `ed6a96291ad135db77940cd51389fdd6516dd0a8` (base epoch `064d14af4f1f9819b76ae0ab4a9cff01efcf6983`), result `4d203f6a232ba91a3842f3432bf65d1a0b257109966059b65708493d0ae6c56a`: all 13 primary outcomes, shared fields and 5,582 charges agree |
| `exploratory/` (3 runs) | `24a57135fc5d86e70e668880d8119556a40a9611` (amended v5, Amendment 2) | `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b` | V1 `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` | configuration label `amendment-1-20261009`; scored under Amendment 2 | scorer epoch `064d14af4f1f9819b76ae0ab4a9cff01efcf6983` (`refit-preparation-20261010`): primary agreement on every checkpoint for all three; see each `RESULT.md` |
| `reference/V1-amended/` | `24a57135fc5d86e70e668880d8119556a40a9611` | `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b` | V1 `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` | as above | accepted within the amended family, result `c4f5fe3d7e180c21217602bca42182fd38954391026f83e53ae38e11d1b973ef` |

The hardened runtime differs from the amended runtime in two things only: a successful `finish` returns a compact summary (at most 956 bytes) with a hashed reference to the full finish record, and refusal messages name the submitted identifier and the failed predicate without stating the correct answer. Checkpoint rules, durations, mistake assessments, part identities and removal predicates are unchanged, and the five configurations are byte-identical between the two epochs. No model run has used the hardened epoch.

Amendment 1 (2026-10-09T23:15Z): CP04 accepts either documented loosening order (the manual diagram 10, 9, 8, 7, 6, 3, 4, 5, 2, 1 or exact reverse 10 to 1); CP12 keeps a new head gasket mandatory and allows the valve-cover gasket to be new or the original inspected and refitted with sealant. Amendment 2 (2026-10-10T00:45Z): one complete documented loosening sequence used consistently across all passes. Both predate every model run.

## 5. Provenance: sealed records and the public form

Each public record was derived from a sealed record kept in the publisher's private evidence packets. The sealed packets were verified before export (every outer inventory `sha256sum -c` OK; the 13 family records equal in the packet's outer copy and its archive; the three exploratory journals equal the inputs the independent scorer sealed).

The sealed records embed strings that this public tree must not carry: two internal shared-folder spellings of benchmark policy documents (cited 625 times per record inside the configuration's reassembly requirements), and the digests of a printed service manual's locator and of two private citation records (one of which is cited by every action's labour charge). Because those strings sit inside the hash-chained configuration and inside every action, they cannot be edited in place without breaking replay. The public records were therefore **re-derived**: the sealed action journal (every action name and input, in order) was replayed through the sealed runtime of the record's epoch against the public configuration, and the runtime wrote a fresh record. The public configuration is the sealed configuration with exactly these changes:

1. the two shared-folder spellings replaced by `benchmark-policy/STUDY-DESIGN-v2.md` and `benchmark-policy/CHECKPOINTS-SIGNOFF.md`;
2. the citation-digest keys for the printed service manual (source M: locator, locator record and external table digests) and for the two private citation records (S7 and S8: document digests and proposal-input record digests) removed, and the two qualification sentences that referred to those digests reworded to say they are withheld ("a printed service manual, not redistributed");
3. the reviewed reference script re-pinned to the corrected service-corpus digest (`repair_scoring.reference.service_sha256`, `repair_scoring.reference_sha256`), since the runtime verifies that pin at start-up;
4. three derived digests recomputed over the published inputs: the analyst time policy's `labor_content_sha256` and its S7 `labor_source_record_sha256` (both computed over the published labour table), and the reassembly checklist's `source_raw_sha256` (the published checklist bytes). The first public derivation had kept these three at their sealed values; the independent scorer refuses such a record (`labor-policy`), so every record was derived a second time, by the same procedure, against the configuration the published environment generates. That configuration is byte-identical to `env/configs/` and is regenerated byte for byte by `python3 -m headgasket prepare`.

Nothing else changed: for every record, at each of the two derivations, the re-derived output equals the scrubbed sealed record in every field except the hash fields that depend on the configuration pin (`config_sha256` including `initial_state.identity.config_sha256`, the reference pins, every `pre_state_sha256`/`post_state_sha256`, `initial_state_sha256`, `final_state_sha256`, the `previous_action_sha256` chain, `score_sha256`, and `report.json` `run_sha256`). Points, failed checkpoints, bolt and checklist results, mistakes, charged seconds, refusal texts and tool outputs are identical. Each `provenance.json` lists the sealed hashes beside the public ones; the independent scorer's results (summarised in each exploratory `independent-score.json`, field `scored_record_sha256`) name the sealed hashes they scored.

| Run | Public `run.json` | Public bytes | Sealed `run.json` | Sealed bytes | Public `actions.jsonl` | Public `report.json` |
|---|---|---:|---|---:|---|---|
| `family/V1-correct` | `bcdac52849f235e517bb7029354d1c47175c053706013b08275a4dedf8d3c031` | 5,513,450 | `78a81192cc3853ad8209085a473958c624c4758cc7c8326eb5ccb286453c0543` | 5,638,747 | `9644840ad0ede304552817c786e93a36a7096b4a7b556e6f74edce6eba2d9c2b` | `361bd8e224b22269b05486ffd358040bc0391c2b97eeb9b1515b7a93c6252ce7` |
| `family/V1-missing_attachment_restoration` | `5a89266599f0c3f06ee01512f57737ea0caba2209cce863368c87e4febb54a9c` | 5,131,775 | `07a459ade6bfd9449682eeb369ed94b3265156a29569a82eda552b982150cd4c` | 5,229,472 | `eb0930f8492912ea7d313a95c4f579f167269ad7a4cc77748cf65a14770473d1` | `563c701c14654e2d83154503facf921d86a45405ce7d12cf4b6b5f8a4de82d3b` |
| `family/V1-skipped_final_stage` | `d0db6f38b7e78a7a0aa2488f267327d5af26251f4745ae9259e492348b7007c2` | 5,483,463 | `9e0281cd4a41f00dd1f72bac20a8eb01c1663a0c322f3818400c61294efc25ea` | 5,606,000 | `4c92495d272ffc0413576d4458027df0a4e246d076d4590e00d586b09748024d` | `0ccf577207f20aa4422dcd513e7e37703ba8ca80183f3572b6918e446b89e856` |
| `family/V1-under_torque` | `11cbd22cdca36ee09b56a42aeeb9d95f26df0f6bbf4ee7daebedcd9a94041a5c` | 5,549,850 | `7a048a94edbd7bf62d962b7fc0f28a253de97c5b69ed95183d3a81ed97d5cc31` | 5,675,147 | `7c33d86f87646f9fd8b0cce61ef6688e7a5b6648e58115c7c72ebfdc0a190817` | `a3030ed9d39d61f1f729acb564f0a469c511170f907740e904c774f4b4a97606` |
| `family/V1-wrong_timing` | `7b13c8cb31cea430b202a1734d1cbc325e10389cfb575112b426708244a71ca5` | 5,516,998 | `67c270ece82b04bdaca9b9ec5a44b9dc0c0888cb51216852cad608cb95c10d06` | 5,642,295 | `96e01d7b0043fbd7d6d4758f17e167374bfd582d27fa9ad223699c318acf7b4f` | `9e045b5259eeacc630a0775cb0657c66c164e3c104d5ceff941f1ec544b3042a` |
| `family/V1-wrong_torque_sequence` | `a36094816a14ffa2d68d6ab50f707af19d4637f8aa5040b4941e2bf06077af7e` | 5,584,126 | `37413c4a59e1e848bf6c6f56d8d4a184945a88fea6f11c83f3b2f5c2d7e76522` | 5,709,423 | `352a72eb3ecf3ec91d6bb3cd76ba745dc1187a77d53a79e485e765ff99153d6e` | `ddba3f86dbe5cc6ce3f5ec0ab446e9903dcd6feb29808006613b6d6e513d34db` |
| `family/V2-correct` | `b13ea67ffb52670859864705656e558821ad4ce61642ac0d527d0fdb9c5c3150` | 5,523,518 | `90b29e9a0d641f33b0b09dad08d58c7a533baa8f214459ed9a96b21f6a76cba1` | 5,649,643 | `192469d822099147c659752178408b2104bd92868968a1ec07180d0e33a8cf19` | `30316269270810e28c6aa7350227f2c06714207383acb918f5a9989373127df2` |
| `family/V2-reused_stretched_bolt` | `0e50b01f45e464a8b7d840aa6d0c40fb70697bac356cfb586d6323280fea420c` | 5,524,011 | `662e9b771f552f2fb2742f1e7637f386842a82b6da7314b8724d982de3d1b3c0` | 5,649,860 | `e46aafd2e94771c990331746855e54185310d21a489ff0af6df4b7d8d579f724` | `b22729ba4fac8664d7324da2ad42df834d79df106c62cd5c041ffb7d4a3487f3` |
| `family/V3-correct` | `7baee26d7bc67d07002aceaa47b464b8bab715327d7c7c0eca349eccf2c506fc` | 5,526,541 | `5c0af381611c5b83bbbc3c1a19c204d7ca9669e374828b6f90b5bc4554cf5948` | 5,652,942 | `650bdc21900e499cfd685a9e33c5cd5689d0de1465bb823c182014be5c51f0fe` | `287a5dbb474307438e71dc2e89744d62e785f319d060c7b061c78b095a683145` |
| `family/V3-correct-replacement-head` | `a8643bb2ef66302757a5c53fbbfc5375134911f91278b2b227f2dfdea9a42d4d` | 5,526,150 | `d202a853077dc39a237e04ab78afe46f4b37a00257ea4f3fc2927eec0bb06e3a` | 5,652,551 | `c721d65fdf838ece03516ecad8a380469528588ef981acbf1897daa8e0ed3611` | `4623983599eeb0a44b0157d13f81015b7cc0cb11eed398fbaede671d63d1cfc6` |
| `family/V4-correct` | `1bab79f9e32218a19957b1e220fea612499c246423cbc76b9a2619ea4237fe7f` | 5,525,780 | `e1a3b490871ba3981fb91c3825b349140b214b500246815e627a5db2835b7f38` | 5,652,181 | `15fafbfb7613123170004fd8d29c2f7a2dad5a5d2ba4568c936874ce1306e855` | `393c9f046bb764da38836ea7a57845d5448cae41a7c5350413a9324816aed645` |
| `family/V4-wrong_gasket` | `89be39dec91dff43c44659c757bf3a7611d7446d55e47328f8035248db45f975` | 5,530,019 | `65d0179e5030d86afed5ab72d2f3e8e04eb5941796f17703c498a09931eb4ee7` | 5,656,420 | `cb8ce9e1a519ac06a866bdcdfc1f05afc6ac3c2f099598dbdf4679d6f2ef98eb` | `409bcde6292f1f35f35da9a6ac53917ac7b23fb978cc56f038bb238c82662ef7` |
| `family/V5-correct` | `6ed99dffe2c9f5db29512eb6828c5d07556428b021f82fa350fc868561f87c4f` | 5,523,431 | `35cc154dbba236c1bc0f7a8b3162b0c97472424f2a508d10f8f4674b64e09a2c` | 5,649,556 | `caac32a24d779ae73e8de46afdccca7366b32fd374fac19687f77698bf6fe01d` | `dd3c1a4c7c2a6d1c240312b3db710519e66415042b6dd53f633fc1ec71e171c9` |
| `exploratory/gpt-6.1-sol` (withheld) | `18c7137c1d0e8491188811f3d960d1fa8226e01ef4ada5102009bd88e8e60430` | 8,049,727 | `68cafb058c150977ff3e21a91f034d03b385148cba99b54399c370e4ab789c7d` | 8,176,024 | `6eb856d2031864d2c7611b2ac25ee9302d8dd00936d07b00aa1873b0ecf6d26d` | `bc2545591ab821c05b86b4d030ba7fae6b7ab5ed2d76d23f87c93833bc7266c8` |
| `exploratory/gpt-6-astra` (withheld) | `df2033e5eda8c5998094e8e2eaa9b3b70315068f5b382c6875e057c46c26b7cf` | 7,403,973 | `de05145dcd32de8cda6bf306a3f98881f8e4cc66a39d478071432362b7236b08` | 7,553,910 | `18e3fbb49c6620f3bc09b1bec5b523818d9a0bab8db6568c2aec10d9db5418fd` | `b3967b4816971fd9886aba930007913cc4de22160eda9af7a16722bdf2089379` |
| `exploratory/gpt-6-luna` (withheld) | `297d4d877ad0ec33fc37eaaafc767706d4a976ed1df2cf1dd4b789bdd728d257` | 10,893,050 | `47aa83bd91c98ef080400e790ad72213b09caad4c6829abadb2ab0b706298fc3` | 11,120,931 | `dffa2cd6dcce5f64e755cf2ecaa81172b3953160abf0398753945f1fbb944022` | `258102e5b3e3893f0c63b8a2a89beb0b3d0d3905521d8ab20bfcf077c09bbcd7` |
| `reference/V1-amended` | `380c18f0420b7130d9d00ec4748e55a7b86ba6255a46e95ab249954989e02f98` | 5,513,396 | `2a6bf37bf36d01d27bc2e0a2ce2a0776bd388af84dec7b473f89804770b6dec8` | 5,638,693 | `bf14904d2ac70eef4898f7cae8eb0483c0a324b16b3ffb737311a76f361d1d1e` | `837e52fd7b16f29121a05449f044e386f94cb19c8a802197575424291a79c708` |

Sealed packets: hardened family `env/hardened-v6-aecadda` (inventory `1290c7fa9a364ac8db4dcb005d305f18183574273581099878a211267f58977f`, family inventory `541c5e4f13f19c056fb9bd51e4a84a8f07f0e96b26d1a28d85eb041690f7b85e`); amended epoch `env/amended-v5-24a5713` (inventory `5404dcfbe2145f697eaafe257103b22ae4902097bd5bb14ace77a9f15839ed17`); independent seals `repair-sol-v2-amendment2-v1` (`2d64a5ae6d97e0c58874e1ff15efdcf9a1122d4473f99a69e024654b536018a5`), `repair-astra-v2-amendment2-v1` (`96c4bd4a1efa00eb612a29f24e1fce604675bfcc56e10864083670f9a606b4bc`), `repair-luna-v2-amendment2-v1` (`4c658724e3095d53ee1ada61e039b65c93ba75614718cb433a6bf3a0aac9e894`), corrected scorer epoch `repair-corrected-scorer-epoch-v1` (`3348ff7070059e739198622621f9d334f17b2e2842913ee2e1b8deea9a20e5b3`).

## 6. Verification performed before publication

- First derivation (with a private copy of the sealed runtimes, never the sealed packets themselves): each of the 17 public records replayed in a fresh process with `tools.variant_demo --worker replay` against its public configuration and manifest, exit 0, bytes identical; each of the 17 sealed records replayed the same way against its sealed configuration; zero differences beyond the hash fields.
- Second derivation (the published records): each record re-derived with the runtime shipped in `env/`, zero differences beyond hash fields from the first derivation. Then, from `env/`, `python3 -m headgasket replay` and `python3 -m headgasket verify` on the 13 family records and the reference: 14/14 exit 0, exact, without `--allow-unlisted-config`; `../scorer/hgj_scorer.py score` on all 17 records: accepted, primary comparison `agreement`, no shared-field disagreement, and the same points, checkpoints, seconds and mistake labels as the sealed independent results. The three exploratory records were replayed the same way (exit 0, exact) before their journals were withheld.
- Each `provenance.json` quotes its replay line.

## 7. Results at a glance

Scripted family (hardened runtime; software controls, no model; every case replays exactly, twice, in the sealed packet):

| Case | Points / 18 | Failed checkpoints | Productive s | Penalty s | Actions | Typed incidents |
|---|---:|---|---:|---:|---:|---|
| `V1-correct` | 18 | none | 13,630 | 0 | 436 | none |
| `V1-missing_attachment_restoration` | 16 | CP12 | 10,630 | 30 | 336 | missing_attachment_restore 1 |
| `V1-skipped_final_stage` | 16 | CP10 | 13,510 | 12 | 426 | missing_torque_stage 1 |
| `V1-under_torque` | 16 | CP10 | 13,510 | 240 | 436 | wrong_torque_value 10 |
| `V1-wrong_timing` | 16 | CP11 | 13,600 | 150 | 436 | timing_marks_off 1 |
| `V1-wrong_torque_sequence` | 14 | CP09, CP10 | 13,390 | 840 | 436 | wrong_order 20 |
| `V2-correct` | 18 | none | 13,720 | 0 | 439 | none |
| `V2-reused_stretched_bolt` | 15 | CP07, CP12 | 13,660 | 60 | 438 | reused_stretched_bolt 1 |
| `V3-correct` | 18 | none | 14,950 | 0 | 440 | none |
| `V3-correct-replacement-head` | 18 | none | 13,780 | 0 | 440 | none |
| `V4-correct` | 18 | none | 13,780 | 0 | 440 | none |
| `V4-wrong_gasket` | 14 | CP08, CP12 | 13,750 | 60 | 440 | wrong_gasket 1 |
| `V5-correct` | 18 | none | 13,720 | 0 | 439 | none |

Exploratory model runs (variant V1, one run each; descriptive only; Success 0 for all; technician seconds are analyst estimates):

| Requested model | Finished in the saved job | Points / 18 | S_partial | Failed checkpoints | Productive + penalty s | Mistake events | Tool attempts (refused) | Agent wall s |
|---|---|---:|---:|---|---|---:|---:|---|
| `gpt-6.1-sol` | no | 3 | 0.083333 | CP02, CP04, CP05, CP07, CP08, CP09, CP10, CP11, CP12 | 13,280 + 12,012 = 25,292 | 245 | 663 (31) | 1,079.566 s |
| `gpt-6-astra` | yes | 15 | 0.416667 | CP02, CP04 | 16,190 + 1,404 = 17,594 | 30 | 528 (15) | 555.098 s |
| `gpt-6-luna` | yes | 13 | 0.361111 | CP02, CP05, CP12 | 15,230 + 14,970 = 30,200 | 309 | 807 (117) | unknown |

Reference (scripted, zero model calls): 18/18, 13,630 + 0 s, 436 actions.

## 8. What these records are not

- Not a leaderboard and not a model comparison: one run per model, one variant, no repeats, no served-model attestation.
- Not measured labour: every second is a cited analyst estimate from the configuration's labour table and mistake-time policy.
- Not physical validation: the environment is a deterministic procedure state machine over a labelled geometry; no joint, soak or engine physics is in the score.
- Not the raw host session and not the agent traces: the collector's private transcripts and close records are not published, nor are the per-action journals of the three model runs; only the scripted records, the model runs' scored results and the harness's summary counters are.
- Model-call counts (Steps) and API-equivalent cost are unknown for all three runs; the host telemetry did not expose them and no rates were applied.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
