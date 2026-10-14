# Changes in v25 (public release build) relative to the audited v24 build

v24 was built on 2026-10-10 from the coordinator's editorial brief and audited (native audit, owner audit, page review, independent number audit). v25 is the public-release build of the same report: every number, table, figure and caveat of v24 is kept exactly; the changes below are presentational and bibliographic. Each change is applied by the lane's own compose step (`tools.editorial_v24`, driven by `data/editorial-v25.md`), not by editing outputs, and the full pipeline (receiving, compose, FODT, headless LibreOffice, native audit, owner review, page review, 184 tests, independent number audit) was repeated on the result.

| Output | v24 SHA-256 | v25 SHA-256 |
|---|---|---|
| paper.pdf | `21f794b82d22c9a76f6a9ee957a5aec5671ff64e876b3426856e3d49e1be0fa8` | `58a1af794123fbb17a623ecf03eac16342db9c19a8fa5b1724e286e446925824` |
| paper.docx | `bf0c9eeccae526a9fa7dc43cb63349a98c9d683672e2b90cf82c5ec58ba7e252` | `72ddf453dc20bf255f8dfcbd3adeaf8aaeecafb555ad8a3997e69b5112316c31` |
| paper.txt | `adccfc205bc67746e5c74e5f4ae419f6e13eac23772194527ac6b05d7727b475` | `264319b12ce0f949fb7d8da57f667e845596ba0437e6c1dd01c15d541ef8eed8` |

Page count: 64 in both builds (body pages 1-14, appendices 15-64). 34 of the 64 rendered pages are byte-identical to v24; the other 30 reflow only by the changes below.

## 1. Title page (author, date, contact, licence)

Why: the owner directed a named author line; a public report needs a date, a contact and a licence statement. The v24 title page carried only the company name.

Before (title page, one line under the title):

> ToolsEnabled, Inc.

After (four lines under the title):

> Joshua Pinckard · ToolsEnabled, Inc.
>
> October 2026
>
> Contact: support@toolsenabled.ai
>
> Text and figures of this report: CC BY 4.0. Benchmark code: MIT licence, released separately.

The delivered Word and PDF document properties now carry the title and the author line (they were empty in v24).

## 2. Dangling spaces before punctuation (70 occurrences)

Why: v24 removed the bracketed internal source keys (for example `[design; environment; service]`) but left the space that preceded each key, so 70 sentences ended with " ." (and two of them inside the paragraphs changed in sections 5 and 6 below). The compose step now removes a space that is immediately followed by a full stop, comma, semicolon or colon. No word changed. The complete list of affected passages is in the appendix of this file.

## 3. Section numbering and table caption

Why: Section 7 had one subsection numbered 7.3 with no 7.1 or 7.2 (the number was carried over verbatim from the editorial brief), and Table 1's caption repeated the section number.

Before: `7.3 Common failures` — After: `7.1 Common failures`

Before: `Table 1. 7 Experimental results` — After: `Table 1. Experimental results`

All other table captions are unchanged (their section titles carry no number).

## 4. Figure 2 caption note

Why: in the sealed source render used for Figure 2 the vertical-axis label "Z mm" overlaps the "-200" tick label. The render is a sealed packet member whose bytes the audit pins, so it cannot be re-laid out without changing audited data; the caption now states the limitation.

Before:

> Figure 2. Lubrication component representation. Separate bodies and their context are preserved. This view does not establish an unobstructed service path .

After:

> Figure 2. Lubrication component representation. Separate bodies and their context are preserved. This view does not establish an unobstructed service path. In the source render the vertical-axis label overlaps one tick label; the illustration is reproduced without alteration.

## 5. Introduction: relation to Engine Bench

Why: the owner asked for one plain sentence placing this benchmark after Engine Bench, which uses the same engine model.

Before:

> We study a head-gasket replacement on a real 1990s 1.6 L SOHC inline-four. The agent works through tools against a detailed CAD-based engine model on a prepared service stand. The surrounding vehicle is outside the task. Specifications must be found in the service-information corpus rather than supplied in the task prompt .

After:

> We study a head-gasket replacement on a real 1990s 1.6 L SOHC inline-four. The agent works through tools against a detailed CAD-based engine model on a prepared service stand. The surrounding vehicle is outside the task. Specifications must be found in the service-information corpus rather than supplied in the task prompt. This benchmark follows Engine Bench (https://toolsenabled.ai/bench/, code at https://github.com/ToolsEnabled/engine-bench) and uses the same engine model: Engine Bench asks an agent to build the engine, and this benchmark asks it to repair one.

## 6. Section 8: relation to Engine Bench

Before:

> A repair environment can test whether an agent uses information while maintaining a changing physical-state model. The application extends a professional-task benchmark pattern into mechanical procedure execution through software tools. Its value depends on accurate task constraints and evaluators, not on adding a new aggregate score.

After:

> A repair environment can test whether an agent uses information while maintaining a changing physical-state model. The application extends a professional-task benchmark pattern into mechanical procedure execution through software tools. Its value depends on accurate task constraints and evaluators, not on adding a new aggregate score. Engine Bench and this benchmark share one engine model and together cover building the engine and repairing it; both are published at https://toolsenabled.ai/bench/, with code at https://github.com/ToolsEnabled/engine-bench.

## 7. Numbers, tables and caveats

Unchanged. The claim ledger (`claim-to-data.csv`) carries 905 claims: the 902 v24 claims plus three new literal claims for the digits on the title page and in the subsection number ("2026", "4.0", "7.1"), each bound to `data/editorial-v25.md`. The native audit reports 885 used claims and 964 numeric occurrences (v24: the same report plus the three new literals). The independent number audit (the scorer lane's `audit_paper_numbers_v24.py`, run read-only against the v25 commit) is recorded in `number-audit-v25/RESULT.json`.

## 8. Source-registry spelling of the editorial brief

Why: five tracked files recorded the v24 editorial brief under a host home-directory spelling of the shared folder; the lane convention is the shared-folder spelling used for every other source. (In this public repository every shared-folder locator in `claim-to-data.csv` is further rewritten to a `sealed:<lane>/<packet>/<path>` locator; see `README.md`.)

Before (in `data/owner-directions.json`, and derived into `data/sources.json`, `evidence/receiving.json`, `manuscript/claim-to-data.csv`, `manuscript/source-register.txt`): a host home-directory spelling of the shared folder (the same brief, `EDITORIAL-v24.md`, under a private mount path)

After: the shared-folder spelling of `EDITORIAL-v24.md`, published here as `sealed:benchmark-policy/EDITORIAL-v24.md`

The brief's bytes and hash (`4a0c06aa…`) are unchanged; receiving, compose, the results build receipt and all audits were repeated so every receipt pins the corrected registry.

## 9. Release documents

`README.md`, `BENCHMARK-CARD.md` and `REPRODUCIBILITY.md` were still the v23 wording ("Prepared for owner review", "assigns no licence", "owner-review draft"). They now state: the 64-page report; the three runs by model name (GPT-6.1-Sol, GPT-6-Astra, GPT-6-Luna, run through Codex CLI) with the one-run-per-model caveat; that Table 1's scripted reference is the amended-rule trace (18/18, 13,630 productive seconds, no penalty) while the original-rule references (14,050 s standard) stay in Appendix F; the licences (report text and figures CC BY 4.0; benchmark code MIT, in its own repository); the support channel (issues on the GitHub repository ToolsEnabled/head-gasket-bench, and support@toolsenabled.ai); and the relation to Engine Bench. `interfaces/PAPER-BUILD.md` no longer says "58 pages, including 43 appendix pages". The owner-review document (`data/owner-review.json`) pins the refreshed files by hash; its text is otherwise unchanged.

## 10. Tooling changes (all in the lane, all re-audited)

- `tools/editorial_v24.py`: residue removal in `clean()`; title-page blocks, subsection heading, Figure 2 note and the two Engine Bench sentences read from `data/editorial-v25.md` (numbers bound as claims); table captions strip a leading section number; the editorial receipt records `release_sha256`.
- `tools/fodt.py`: `TitleNote` paragraph style for the title-page lines after the author line; document metadata (title, creator) written into the FODT so the Word/PDF properties are filled.
- `tools/prepare_inputs.py`: receives `data/editorial-v25.md` as an authored paper source (`editorial-v25.md`, origin `current-paper-source/data/editorial-v25.md`).
- `data/owner-directions.json`: origin spelling (section 8).
- `evidence/results-figure-review.json`: rebound to the repeated results build; all 118 result outputs including the 32 PNGs are byte-identical to the reviewed build.
- `evidence/all-page-visual-review.json`, `evidence/owner-visual-review.json`: fresh reviews of the 30 changed paper pages and the one changed owner page; byte-identical pages reuse the v24 observations.

## Appendix: every passage changed only by residue removal

Listed by section; "before" shows the v24 text with the dangling space, "after" the v25 text.


### 1 Introduction

- Before: The report distinguishes the task specification from supported software behavior and physical qualifications. Current results describe exploratory standard-job trajectories; the larger comparative collection remains pending. Historical scripted references and model attempts retain their actual rules and evaluator versions .
- After: The report distinguishes the task specification from supported software behavior and physical qualifications. Current results describe exploratory standard-job trajectories; the larger comparative collection remains pending. Historical scripted references and model attempts retain their actual rules and evaluator versions.


### 2 Benchmark desiderata and comparison to other benchmarks

- Before: Our desiderata are a documented service procedure, separate component identities, geometry-based access, stateful tool actions, task-specific deterministic checks, and reproducible initial conditions. Difficulty should arise from the job rather than hidden specifications or arbitrary tool failures. Missing service limits and unresolved access must remain visible .
- After: Our desiderata are a documented service procedure, separate component identities, geometry-based access, stateful tool actions, task-specific deterministic checks, and reproducible initial conditions. Difficulty should arise from the job rather than hidden specifications or arbitrary tool failures. Missing service limits and unresolved access must remain visible.


### 3 Environment

- Before: The game presents a prepared engine, tools, replacement supplies and service information. The interface supports looking, inspection, measurement, service search, removal, installation, cleaning, replacement, tightening, timing checks and final submission. Every action refers to a specific target; attempts and state changes are recorded separately .
- After: The game presents a prepared engine, tools, replacement supplies and service information. The interface supports looking, inspection, measurement, service search, removal, installation, cleaning, replacement, tightening, timing checks and final submission. Every action refers to a specific target; attempts and state changes are recorded separately.

- Before: CAD bodies retain individual identities. A service-body index links procedure names to geometry, but a display or index entry alone does not prove that a part can be withdrawn. Geometry and access checks must determine permitted removal order. Unknown constraints cannot be interpreted as permission .
- After: CAD bodies retain individual identities. A service-body index links procedure names to geometry, but a display or index entry alone does not prove that a part can be withdrawn. Geometry and access checks must determine permitted removal order. Unknown constraints cannot be interpreted as permission.

- Before: Clamp mechanics provide state changes and observations such as bolt stretch, gasket condition and local clamp response. Unloaded service flatness is supplied or measured state; loaded head bow and bolt stretch are model responses. Available models include idealized material and contact behavior. These models support environment realism within their stated scope; they are not a full engine simulation or a validation of service life .
- After: Clamp mechanics provide state changes and observations such as bolt stretch, gasket condition and local clamp response. Unloaded service flatness is supplied or measured state; loaded head bow and bolt stretch are model responses. Available models include idealized material and contact behavior. These models support environment realism within their stated scope; they are not a full engine simulation or a validation of service life.

- Before: Neither a soak nor an engine run is part of scoring. The earlier operating-soak approach was dropped because the intended outcome is completion of the repair procedure against a correct reference. This is a design decision, not an engine-durability result .
- After: Neither a soak nor an engine run is part of scoring. The earlier operating-soak approach was dropped because the intended outcome is completion of the repair procedure against a correct reference. This is a design decision, not an engine-durability result.


### 4 Task structure

- Before: Each task comprises an instruction, a fixed starting state, a service corpus, weighted checkpoints and a deterministic evaluator. The proposed evaluator will read the final state and chronological action record. Binary checkpoint decisions will expose the supporting observations and the reason for each failed check .
- After: Each task comprises an instruction, a fixed starting state, a service corpus, weighted checkpoints and a deterministic evaluator. The proposed evaluator will read the final state and chronological action record. Binary checkpoint decisions will expose the supporting observations and the reason for each failed check.

- Before: The agent is asked to complete the repair, not to reproduce an answer string. The correct scripted baseline supplies the reference procedure and must satisfy every checkpoint. It defines 100% reference accuracy; that requirement is distinct from the complete original-rule references reported separately and from validation under the amended rules .
- After: The agent is asked to complete the repair, not to reproduce an answer string. The correct scripted baseline supplies the reference procedure and must satisfy every checkpoint. It defines 100% reference accuracy; that requirement is distinct from the complete original-rule references reported separately and from validation under the amended rules.


### 4.1 Evaluation metrics

- Before: Technician time is the sum of cited action charges and mistake-correction charges, reported as productive and penalty components beside the scripted baseline. It is charged time, not a measured mechanic’s elapsed time or a simulated delay. Mistakes by type, agent wall time and tool calls are additional measures .
- After: Technician time is the sum of cited action charges and mistake-correction charges, reported as productive and penalty components beside the scripted baseline. It is charged time, not a measured mechanic’s elapsed time or a simulated delay. Mistakes by type, agent wall time and tool calls are additional measures.

- Before: Secondary measures include each of the ten head bolts’ condition, both torque stages and sequence position, plus checkpoint pass rates and failure categories. The explicit head-bolt group defines the denominator; covers and other fasteners do not enter it .
- After: Secondary measures include each of the ten head bolts’ condition, both torque stages and sequence position, plus checkpoint pass rates and failure categories. The explicit head-bolt group defines the denominator; covers and other fasteners do not enter it.


### 4.2 Workflow

- Before: Initialization restores the declared starting state, selects the variant, verifies the environment and evaluator versions, and starts the isolated collector. The task prompt identifies the job; the service corpus supplies specifications. Execution records each tool request, response, state transition and charge. Finalization evaluates the repair and preserves the complete report .
- After: Initialization restores the declared starting state, selects the variant, verifies the environment and evaluator versions, and starts the isolated collector. The task prompt identifies the job; the service corpus supplies specifications. Execution records each tool request, response, state transition and charge. Finalization evaluates the repair and preserves the complete report.

- Before: An end report is required after normal submission, budget exhaustion, early stopping, interruption or an apparatus refusal. It retains observed fields and named unknowns. Calling finish does not by itself establish complete or correct work. Earlier mistakes remain in the action record; the checkpoint specification must state how later corrections affect final accuracy and charged corrective work .
- After: An end report is required after normal submission, budget exhaustion, early stopping, interruption or an apparatus refusal. It retains observed fields and named unknowns. Calling finish does not by itself establish complete or correct work. Earlier mistakes remain in the action record; the checkpoint specification must state how later corrections affect final accuracy and charged corrective work.


### Environment and workflow overview

- Before: Figure 1. Proposed evaluation workflow. Tool observations and actions connect the agent to the engine state; the evaluator uses component state and ordered history. Dashed flow denotes usage telemetry. A complete reference procedure and collector remain requirements for study runs .
- After: Figure 1. Proposed evaluation workflow. Tool observations and actions connect the agent to the engine state; the evaluator uses component state and ordered history. Dashed flow denotes usage telemetry. A complete reference procedure and collector remain requirements for study runs.


### 5 Task creation

- Before: The draft task set varies the condition of the same repair problem rather than introducing unrelated jobs. It includes a standard job, a stretched bolt, a warped head, an incorrect gasket among available parts, and a worn timing belt. Each variant needs a realizable starting state, appropriate observations, a correct baseline and a tested evaluator before use .
- After: The draft task set varies the condition of the same repair problem rather than introducing unrelated jobs. It includes a standard job, a stretched bolt, a warped head, an incorrect gasket among available parts, and a worn timing belt. Each variant needs a realizable starting state, appropriate observations, a correct baseline and a tested evaluator before use.

- Before: Checkpoint curation follows the service procedure. It covers lookup, disassembly, timing preparation, loosening, cleaning, measurement, part choice, tightening and reassembly. Point values express task importance. They must be reviewed and frozen before collecting comparative runs; they must not be tuned to a model ranking .
- After: Checkpoint curation follows the service procedure. It covers lookup, disassembly, timing preparation, loosening, cleaning, measurement, part choice, tightening and reassembly. Point values express task importance. They must be reviewed and frozen before collecting comparative runs; they must not be tuned to a model ranking.

- Before: The historical per-operation labor table consists of analyst estimates and charges successful actions only. Later scripted reports include corrective penalties, also as analyst estimates. Neither establishes the cited professional action-time and correction schedule required by the new design. Labor sources, charge units and rules for blocked attempts and rework remain to be established .
- After: The historical per-operation labor table consists of analyst estimates and charges successful actions only. Later scripted reports include corrective penalties, also as analyst estimates. Neither establishes the cited professional action-time and correction schedule required by the new design. Labor sources, charge units and rules for blocked attempts and rework remain to be established.

- Before: The earlier snapshot did not demonstrate the full task set. Later original-rule records contain complete references for every configured primary variant, including a software head-machining route and a separate head-replacement alternative. These records do not establish physical machining, exact service applicability or completion under the amended rules. Selected component transitions must remain bound to their actual runtime and configuration .
- After: The earlier snapshot did not demonstrate the full task set. Later original-rule records contain complete references for every configured primary variant, including a software head-machining route and a separate head-replacement alternative. These records do not establish physical machining, exact service applicability or completion under the amended rules. Selected component transitions must remain bound to their actual runtime and configuration.

- Before: Each task should specify the starting component condition, the information visible to the agent, permitted service actions and the state or history evidence needed for every checkpoint. For each proposed variant, a reference procedure should demonstrate that the task is feasible under the same tool contract. Review should cover correct completion, plausible incorrect completion and unavailable measurements before model collection. The current task variants are design requirements; legacy fixture names do not establish their implementation .
- After: Each task should specify the starting component condition, the information visible to the agent, permitted service actions and the state or history evidence needed for every checkpoint. For each proposed variant, a reference procedure should demonstrate that the task is feasible under the same tool contract. Review should cover correct completion, plausible incorrect completion and unavailable measurements before model collection. The current task variants are design requirements; legacy fixture names do not establish their implementation.


### 6 Baseline agents

- Before: The planned agent is Codex CLI with only the environment’s MCP tools, run through an isolated collector. The planned model arms are GPT-6.1-Sol, GPT-6-Astra and GPT-6-Luna. A Claude arm is a possible later extension .
- After: The planned agent is Codex CLI with only the environment’s MCP tools, run through an isolated collector. The planned model arms are GPT-6.1-Sol, GPT-6-Astra and GPT-6-Luna. A Claude arm is a possible later extension.

- Before: The scripted correct repair is the environment reference, not a competing language model. It must execute the intended job with valid access and actions and satisfy the complete checkpoint set. Deliberately incorrect jobs test evaluator sensitivity to wrong order, wrong torque, omitted stages, incorrect parts, missed measurements and timing errors .
- After: The scripted correct repair is the environment reference, not a competing language model. It must execute the intended job with valid access and actions and satisfy the complete checkpoint set. Deliberately incorrect jobs test evaluator sensitivity to wrong order, wrong torque, omitted stages, incorrect parts, missed measurements and timing errors.

- Before: The exploratory run budget and earlier attempts remain in the accounting. Actual standard-task observations are reported below; the larger model-by-variant matrix remains pending. Requested and served model identifiers, transport refusals and stopping states retain their recorded meanings .
- After: The exploratory run budget and earlier attempts remain in the accounting. Actual standard-task observations are reported below; the larger model-by-variant matrix remains pending. Requested and served model identifiers, transport refusals and stopping states retain their recorded meanings.


### 8 Implications and future directions

- Before: Future work should complete the service-to-geometry mapping, validate references under the amended rules, validate the technician-time estimates against published labour-time guides and extend the original-rule software checks to the selected collection runtime. Collected trajectories can then support analysis of procedural decisions and resource use. Broader tasks and physical execution require separate evidence .
- After: Future work should complete the service-to-geometry mapping, validate references under the amended rules, validate the technician-time estimates against published labour-time guides and extend the original-rule software checks to the selected collection runtime. Collected trajectories can then support analysis of procedural decisions and resource use. Broader tasks and physical execution require separate evidence.

- Before: The benchmark does not certify that an agent or robot can safely repair an engine. It omits the surrounding vehicle, workshop dexterity and many material uncertainties. ToolsEnabled, Inc. develops the environment and authors this report; this relationship should be considered when interpreting the design. The exploratory attempts do not establish comparative population performance .
- After: The benchmark does not certify that an agent or robot can safely repair an engine. It omits the surrounding vehicle, workshop dexterity and many material uncertainties. ToolsEnabled, Inc. develops the environment and authors this report; this relationship should be considered when interpreting the design. The exploratory attempts do not establish comparative population performance.


### Appendix B. Environment and engine model

- Before: The service-body index contains 1240 selected body rows. Individual bodies remain distinct, including hardware candidates and contextual geometry. The mapping provides a basis for task-specific access checks; it is not proof of a complete legal disassembly route .
- After: The service-body index contains 1240 selected body rows. Individual bodies remain distinct, including hardware candidates and contextual geometry. The mapping provides a basis for task-specific access checks; it is not proof of a complete legal disassembly route.

- Before: The inherited interface includes a historical operating-harness endpoint. Its action signatures can support the revised design, but its previous finish behavior is not evidence of the new checkpoint evaluator .
- After: The inherited interface includes a historical operating-harness endpoint. Its action signatures can support the revised design, but its previous finish behavior is not evidence of the new checkpoint evaluator.

- Before: The service corpus distinguishes published service information, private source references, benchmark procedure choices and estimates. Selected torque transcriptions differ, reuse limits are incomplete, and gasket orientation and dowel fit need explicit support. Those gaps must be resolved or declared before a task can claim a determinate correct answer .
- After: The service corpus distinguishes published service information, private source references, benchmark procedure choices and estimates. Selected torque transcriptions differ, reuse limits are incomplete, and gasket orientation and dowel fit need explicit support. Those gaps must be resolved or declared before a task can claim a determinate correct answer.

- Before: The environment exposes component observations and state-changing actions through an interface. Existing software demonstrations support component identity and selected action behavior. The engine display supplies geometric context, while the mechanical models make finite, assumption-dependent predictions. A complete display does not establish a usable service path, and a model response does not validate the service procedure. Material history, unloaded flatness and loaded deformation must be distinguished when defining measurements .
- After: The environment exposes component observations and state-changing actions through an interface. Existing software demonstrations support component identity and selected action behavior. The engine display supplies geometric context, while the mechanical models make finite, assumption-dependent predictions. A complete display does not establish a usable service path, and a model response does not validate the service procedure. Material history, unloaded flatness and loaded deformation must be distinguished when defining measurements.


### Appendix B. Benchmark construction

- Before: Construction links the service procedure to observable component state and permitted actions. The following review stages separate task feasibility from evaluator behavior; none substitutes for a completed reference run .
- After: Construction links the service procedure to observable component state and permitted actions. The following review stages separate task feasibility from evaluator behavior; none substitutes for a completed reference run.

- Before: Reviewers should inspect a complete example from instruction through final report. Changing a service threshold, active component identity or evaluator condition changes the task definition and requires a new reviewed configuration. Historical software tests remain tied to the versions they exercised .
- After: Reviewers should inspect a complete example from instruction through final report. Changing a service threshold, active component identity or evaluator condition changes the task definition and requires a new reviewed configuration. Historical software tests remain tied to the versions they exercised.

- Before: The factory-style path lifts a mapped rocker assembly of 109 bodies with 15 bolts retained in that group. It requires 14 releases of head threads and 16 adjuster backoffs; the camshaft remains installed and needs independent support. A full-strip path remains a valid alternate. Group retention, support and unobstructed withdrawal retain provisional geometric qualifications .
- After: The factory-style path lifts a mapped rocker assembly of 109 bodies with 15 bolts retained in that group. It requires 14 releases of head threads and 16 adjuster backoffs; the camshaft remains installed and needs independent support. A full-strip path remains a valid alternate. Group retention, support and unobstructed withdrawal retain provisional geometric qualifications.

- Before: For the default fixture, the grouped route has 162 removal operations and 51 moving groups, compared with 185 operations and 71 groups for the full-strip route. Both restore 626 removed positions and retain 614 bodies. Alternative stay choices carry their own checklists. These are removal-fixture counts, not complete repair action counts or technician seconds; neither path is physical service validation .
- After: For the default fixture, the grouped route has 162 removal operations and 51 moving groups, compared with 185 operations and 71 groups for the full-strip route. Both restore 626 removed positions and retain 614 bodies. Alternative stay choices carry their own checklists. These are removal-fixture counts, not complete repair action counts or technician seconds; neither path is physical service validation.


### Appendix B. Engine geometry

- Before: Figure 3. Integrated engine display. The original component geometry is shown without changing its body identities. Display completeness does not resolve all access and intersection questions .
- After: Figure 3. Integrated engine display. The original component geometry is shown without changing its body identities. Display completeness does not resolve all access and intersection questions.


### Appendix B. Mechanical assumptions

- Before: The mechanical model links bolt loading, gasket compression and head response. The historical rigid model and later elastic plate approximation have different scopes. A linear elastic mechanical plate with a yield exclusion must not be described as a model of permanent head deformation .
- After: The mechanical model links bolt loading, gasket compression and head response. The historical rigid model and later elastic plate approximation have different scopes. A linear elastic mechanical plate with a yield exclusion must not be described as a model of permanent head deformation.

- Before: Separate generic material-law work carries gasket recovery, bolt stretch and sectional material history. Its parameters and applicability are not selected-part validation. Finite order comparisons show that an action history can affect transient component response; they do not establish lasting damage, reliable repair classification or engine durability .
- After: Separate generic material-law work carries gasket recovery, bolt stretch and sectional material history. Its parameters and applicability are not selected-part validation. Finite order comparisons show that an action history can affect transient component response; they do not establish lasting damage, reliable repair classification or engine durability.

- Before: Material proxies, contact reduction and finite comparison limits remain explicit. Mechanical state is used to make inspection and measurement meaningful. Checkpoint correctness is determined by the reference procedure and recorded work, without operating the engine .
- After: Material proxies, contact reduction and finite comparison limits remain explicit. Mechanical state is used to make inspection and measurement meaningful. Checkpoint correctness is determined by the reference procedure and recorded work, without operating the engine.


### Appendix B. Finite component illustration

- Before: Figure 4. Finite component-model predictions retained as an illustration of mechanical assumptions. The dashed inherited-model reference does not validate the added plate model. Recovery and material properties are estimates. Positive margins for incorrect command sequences are not evidence of a correct repair .
- After: Figure 4. Finite component-model predictions retained as an illustration of mechanical assumptions. The dashed inherited-model reference does not validate the added plate model. Recovery and material properties are estimates. Positive margins for incorrect command sequences are not evidence of a correct repair.


### Appendix C. Task and checkpoint details

- Before: These variants are a draft task set. All checkpoints retain their normal meaning when an abnormal condition is absent. Variant identifiers are task labels, not observed samples .
- After: These variants are a draft task set. All checkpoints retain their normal meaning when an abnormal condition is absent. Variant identifiers are task labels, not observed samples.

- Before: Original-rule references cover the warped-head and worn-belt configurations, with a separate head-replacement alternative. This supports the recorded software cases rather than physical machining or part-fit validation. Component identity, condition and timing transitions must be reviewed against the exact amended runtime before comparative collection .
- After: Original-rule references cover the warped-head and worn-belt configurations, with a separate head-replacement alternative. This supports the recorded software cases rather than physical machining or part-fit validation. Component identity, condition and timing transitions must be reviewed against the exact amended runtime before comparative collection.

- Before: A proposed wrong-gasket task offers a specified incorrect gasket alongside the correct replacement. The agent must inspect the assembly, identify the required replacement and complete the applicable service sequence. A final declaration alone cannot demonstrate part identity or ordered torque stages; checkpoint evidence must come from component state and action history. Reassembly checks should distinguish legitimate replacement and disposal from an absent required component. This example illustrates the proposed evaluation contract and is not an observed agent run .
- After: A proposed wrong-gasket task offers a specified incorrect gasket alongside the correct replacement. The agent must inspect the assembly, identify the required replacement and complete the applicable service sequence. A final declaration alone cannot demonstrate part identity or ordered torque stages; checkpoint evidence must come from component state and action history. Reassembly checks should distinguish legitimate replacement and disposal from an absent required component. This example illustrates the proposed evaluation contract and is not an observed agent run.


### Appendix C. Signed checkpoint requirements continued

- Before: Total available points: 18. Each checkpoint is binary, and all checkpoints remain applicable to every task. A correct normal-condition decision can pass a measurement checkpoint without replacing the part .
- After: Total available points: 18. Each checkpoint is binary, and all checkpoints remain applicable to every task. A correct normal-condition decision can pass a measurement checkpoint without replacing the part.

- Before: The current amendments accept either documented loosening sequence, used consistently across all loosening passes, and withdraw the unconditional new cover-gasket policy. The new head gasket remains mandatory. Reassembly restores required components with legitimate replacement and waste dispositions. Final-state corrections may recover credit; chronological process violations and charges remain recorded. Historical commands and reports retain their original source versions .
- After: The current amendments accept either documented loosening sequence, used consistently across all loosening passes, and withdraw the unconditional new cover-gasket policy. The new head gasket remains mandatory. Reassembly restores required components with legitimate replacement and waste dispositions. Final-state corrections may recover credit; chronological process violations and charges remain recorded. Historical commands and reports retain their original source versions.


### Appendix C. Engineering specifications — H01 to H05

- Before: The complete specification table distinguishes public-source support from benchmark policy. The captured public workshop manual identifies its first edition as 9/91. Exact reconstructed-hardware applicability and later manual supplements remain unverified. Policy rows make no factory-value claim. Every source disagreement and row scope is retained below. The table records the earlier checkpoint amendment; the current requirement to use one chosen loosening sequence across all passes appears in the checkpoint table above. Full original fields, source URLs and implementation locators accompany the report .
- After: The complete specification table distinguishes public-source support from benchmark policy. The captured public workshop manual identifies its first edition as 9/91. Exact reconstructed-hardware applicability and later manual supplements remain unverified. Policy rows make no factory-value claim. Every source disagreement and row scope is retained below. The table records the earlier checkpoint amendment; the current requirement to use one chosen loosening sequence across all passes appears in the checkpoint table above. Full original fields, source URLs and implementation locators accompany the report.


### Appendix D. Agent details and harness disclosure

- Before: The collector must restrict the agent to the environment MCP interface and record the full prompt, tool schema, requested model, returned model and execution configuration. Session state and credentials must be isolated from unrelated work. The public report does not disclose account identifiers .
- After: The collector must restrict the agent to the environment MCP interface and record the full prompt, tool schema, requested model, returned model and execution configuration. Session state and credentials must be isolated from unrelated work. The public report does not disclose account identifiers.

- Before: The recorded historical collector includes wrapper and process-recovery evidence. A successful owned-process cleanup test does not prove current model identity, account isolation or production lifecycle behavior. These require tests against the exact collector used for study runs .
- After: The recorded historical collector includes wrapper and process-recovery evidence. A successful owned-process cleanup test does not prove current model identity, account isolation or production lifecycle behavior. These require tests against the exact collector used for study runs.

- Before: Record model calls, tool attempts, successful tool actions, prompt and completion tokens, cache accounting if available, wall-clock start and end, retry events and termination reason. If a field cannot be obtained, report it as unavailable and explain the measurement boundary. Do not infer model calls from tool calls or price from subscription access .
- After: Record model calls, tool attempts, successful tool actions, prompt and completion tokens, cache accounting if available, wall-clock start and end, retry events and termination reason. If a field cannot be obtained, report it as unavailable and explain the measurement boundary. Do not infer model calls from tool calls or price from subscription access.

- Before: Keep configuration and prompt versions alongside every attempt. Retries must retain their prior records. A failure to execute the apparatus is distinct from an agent choosing an incorrect action. Neither a cleanup failure nor a partial response should erase the evidence already collected .
- After: Keep configuration and prompt versions alongside every attempt. Retries must retain their prior records. A failure to execute the apparatus is distinct from an agent choosing an incorrect action. Neither a cleanup failure nor a partial response should erase the evidence already collected.


### Appendix E. Evaluation protocol

- Before: This condensed protocol governs the proposed comparison. The complete historical form and a field-by-field amendment mapping accompany the report. The present design replaces earlier survival endpoints, factorial settings and judge-based scoring; historical records are retained without making them current requirements .
- After: This condensed protocol governs the proposed comparison. The complete historical form and a field-by-field amendment mapping accompany the report. The present design replaces earlier survival endpoints, factorial settings and judge-based scoring; historical records are retained without making them current requirements.


### Appendix E. Current exploratory collection status

- Before: The protocol summary above preserves the reviewed precollection design. Exploratory repair observations are now reported separately in the results sections. The larger comparative collection and confirmatory analysis remain pending. These observations do not amend the historical form, remove review requirements or establish physical repair safety .
- After: The protocol summary above preserves the reviewed precollection design. Exploratory repair observations are now reported separately in the results sections. The larger comparative collection and confirmatory analysis remain pending. These observations do not amend the historical form, remove review requirements or establish physical repair safety.


### Appendix F. Exploratory resources

- Before: One exploratory attempt was observed for each requested model on the standard repair task. The model names identify the model; served model identity was not attested. The collector does not supply model-call Steps or a model-specific API price basis, so those cells remain unavailable. A stopped repair remains in the run count .
- After: One exploratory attempt was observed for each requested model on the standard repair task. The model names identify the model; served model identity was not attested. The collector does not supply model-call Steps or a model-specific API price basis, so those cells remain unavailable. A stopped repair remains in the run count.

- Before: Productive and penalty charges are additive. Mistake events count affected actions; typed labels can overlap. Cache-read tokens are already included in input tokens and must not be added again. Agent wall time excludes setup; tool attempts are not model-call Steps. Recorded telemetry and unavailable observations retain separate meanings .
- After: Productive and penalty charges are additive. Mistake events count affected actions; typed labels can overlap. Cache-read tokens are already included in input tokens and must not be added again. Agent wall time excludes setup; tool attempts are not model-call Steps. Recorded telemetry and unavailable observations retain separate meanings.

- Before: Luna token counters are the latest observed prefix, with final-turn coverage unavailable. They are displayed separately from complete-turn resource measurements and do not supply a complete consumption estimate. Its agent wall time remains unavailable. The accepted finish endpoint preserves the original capture refusal and pending response record; it does not convert that record into a completed model turn .
- After: Luna token counters are the latest observed prefix, with final-turn coverage unavailable. They are displayed separately from complete-turn resource measurements and do not supply a complete consumption estimate. Its agent wall time remains unavailable. The accepted finish endpoint preserves the original capture refusal and pending response record; it does not convert that record into a completed model turn.

- Before: For Sol, the independent scorer recorded 25262 charged seconds, whereas the used in-game classification records 25292. The documented difference is a cover-gasket refit classified as productive work by the independent scorer and as a mistake penalty in the game. The original records are retained. The table uses the in-game policy; primary checkpoint points agree .
- After: For Sol, the independent scorer recorded 25262 charged seconds, whereas the used in-game classification records 25292. The documented difference is a cover-gasket refit classified as productive work by the independent scorer and as a mistake penalty in the game. The original records are retained. The table uses the in-game policy; primary checkpoint points agree.

- Before: The independent and game scorers use different secondary checklist item sets and retain unknowns. Agreement on primary points and shared bolt fields does not establish full service coverage or external contract identity. Astra and Luna shared charge entries agree; Sol retains the stated limitation. Luna also retains an overlapping mistake-label difference between scorers. These model attempts remain separate from the original-rule scripted references and the earlier incomplete diagnostic jobs .
- After: The independent and game scorers use different secondary checklist item sets and retain unknowns. Agreement on primary points and shared bolt fields does not establish full service coverage or external contract identity. Astra and Luna shared charge entries agree; Sol retains the stated limitation. Luna also retains an overlapping mistake-label difference between scorers. These model attempts remain separate from the original-rule scripted references and the earlier incomplete diagnostic jobs.


### Appendix F. Exploratory checkpoint outcomes

- Before: Each column is one repair attempt. Outcomes join checkpoint identity, weight and pass status between the game and independent reports. The full requirements appear in Appendix C .
- After: Each column is one repair attempt. Outcomes join checkpoint identity, weight and pass status between the game and independent reports. The full requirements appear in Appendix C.


### Appendix F. Exploratory head-bolt checks

- Before: Cells give raw criteria passed out of criteria checked. The raw record keeps bolt condition, initial and final torque values, each stage sequence and stage order separate. The study collector’s reduced mapping combines the two sequence checks; its denominator is different. Sol’s removed bolts are an unfinished observation; final accuracy remains unavailable. Correct final bolt checks do not establish correct disassembly, loosening or restoration .
- After: Cells give raw criteria passed out of criteria checked. The raw record keeps bolt condition, initial and final torque values, each stage sequence and stage order separate. The study collector’s reduced mapping combines the two sequence checks; its denominator is different. Sol’s removed bolts are an unfinished observation; final accuracy remains unavailable. Correct final bolt checks do not establish correct disassembly, loosening or restoration.


### Appendix F. Exploratory mistake labels

- Before: An action may carry several labels. The unique event count in the resource table therefore need not equal the sum of these categories. Corrective penalties remain charged even if the agent subsequently corrects the state .
- After: An action may carry several labels. The unique event count in the resource table therefore need not equal the sum of these categories. Corrective penalties remain charged even if the agent subsequently corrects the state.


### Appendix F. Results machinery and scripted checks

- Before: The results software reads saved report data and generates aggregate tables, per-variant and per-checkpoint summaries, per-bolt records, typed mistakes and figures. It does not execute the environment or an agent. The cases below test that reporting path; they are historical scripted procedures, not language-model outcomes .
- After: The results software reads saved report data and generates aggregate tables, per-variant and per-checkpoint summaries, per-bolt records, typed mistakes and figures. It does not execute the environment or an agent. The cases below test that reporting path; they are historical scripted procedures, not language-model outcomes.

- Before: The case name correct is inherited from its producer; the recorded draft checkpoints show that the baseline is incomplete. The reports lack model, agent-arm and current-variant identities. They cannot establish the revised correct reference or populate a model-by-variant results table. The timing fault also shares an already unmet timing checkpoint with the incomplete baseline, so equal aggregate scores do not demonstrate evaluator sensitivity to that fault .
- After: The case name correct is inherited from its producer; the recorded draft checkpoints show that the baseline is incomplete. The reports lack model, agent-arm and current-variant identities. They cannot establish the revised correct reference or populate a model-by-variant results table. The timing fault also shares an already unmet timing checkpoint with the incomplete baseline, so equal aggregate scores do not demonstrate evaluator sensitivity to that fault.

- Before: Charges are analyst task estimates, not measured technician time or a published labor-time standard. Model-call Steps, token counts, API-equivalent Cost and agent wall time are unavailable in these reports. The companion tables preserve those missing values and their reasons; tool attempts remain a separate field. Scripted case means have no inferential intervals and do not populate common-failure findings .
- After: Charges are analyst task estimates, not measured technician time or a published labor-time standard. Model-call Steps, token counts, API-equivalent Cost and agent wall time are unavailable in these reports. The companion tables preserve those missing values and their reasons; tool attempts remain a separate field. Scripted case means have no inferential intervals and do not populate common-failure findings.

- Before: For later model runs, every row must retain the collector identity, task and evaluator versions, original report and telemetry provenance. The reducer keeps interrupted and unsuccessful attempts, checks weighted checkpoint arithmetic and labor-ledger totals, and preserves unknown component observations. Complete means are withheld when a component is missing; any available-case mean has its own denominator. The prepared analysis resamples whole runs within declared variants, never individual bolts .
- After: For later model runs, every row must retain the collector identity, task and evaluator versions, original report and telemetry provenance. The reducer keeps interrupted and unsuccessful attempts, checks weighted checkpoint arithmetic and labor-ledger totals, and preserves unknown component observations. Complete means are withheld when a component is missing; any available-case mean has its own denominator. The prepared analysis resamples whole runs within declared variants, never individual bolts.


### Appendix F. Original-rule scripted references

- Before: These saved procedures complete the original signed checkpoint rules in the environment scorer and the independent scorer. They are scripted references, not model attempts. Each uses the earlier disassembly policy and requires both gaskets to be new; the later allowance for an inspected cover gasket and the grouped rocker route were not applied retroactively .
- After: These saved procedures complete the original signed checkpoint rules in the environment scorer and the independent scorer. They are scripted references, not model attempts. Each uses the earlier disassembly policy and requires both gaskets to be new; the later allowance for an inspected cover gasket and the grouped rocker route were not applied retroactively.

- Before: Both scorers report full completion 1 and partial score 1.0 for each listed reference. Tool actions are not model-call Steps. Productive and penalty seconds are analyst charges, not elapsed mechanic time. The machining route carries a larger charge; the separately recorded replacement-head route is a different procedure and is not pooled into this table .
- After: Both scorers report full completion 1 and partial score 1.0 for each listed reference. Tool actions are not model-call Steps. Productive and penalty seconds are analyst charges, not elapsed mechanic time. The machining route carries a larger charge; the separately recorded replacement-head route is a different procedure and is not pooled into this table.

- Before: Checkpoint outcomes and shared bolt, time and mistake values agree. This does not make the secondary checklists equivalent: the standard case has 1674 environment items and 2799 independent items, with unknown condition observations retained. Evidence descriptions also differ. Full service coverage and modeled checklist completion are not established. The comparison leaves external contract authentication as a separate requirement. These scripts record zero model and provider calls and zero reported API-equivalent cost. A separately computed token-priced Cost remains unavailable without dated rates. Agent wall time is unrecorded .
- After: Checkpoint outcomes and shared bolt, time and mistake values agree. This does not make the secondary checklists equivalent: the standard case has 1674 environment items and 2799 independent items, with unknown condition observations retained. Evidence descriptions also differ. Full service coverage and modeled checklist completion are not established. The comparison leaves external contract authentication as a separate requirement. These scripts record zero model and provider calls and zero reported API-equivalent cost. A separately computed token-priced Cost remains unavailable without dated rates. Agent wall time is unrecorded.

- Before: The older incomplete scripted cases above retain their original records. Neither cohort supplies agent performance or empirical model-failure rates. Runs under the amended rules require their own runtime and evaluator evidence .
- After: The older incomplete scripted cases above retain their original records. Neither cohort supplies agent performance or empirical model-failure rates. Runs under the amended rules require their own runtime and evaluator evidence.


### Appendix G. Limitations

- Before: The model observations are exploratory attempts on a standard configured task. Requested model identifiers are known, but served identities and model-call Steps are unavailable. Geometric visibility, software action checks and finite mechanical predictions establish different aspects of the apparatus; they do not certify physical repair. Factory service applicability, physical machining and fit, full service coverage, external contract identity and professional labor-time sources remain qualified. Earlier incomplete diagnostics and complete original-rule references stay separate from amended-rule model attempts. The larger comparative study remains pending .
- After: The model observations are exploratory attempts on a standard configured task. Requested model identifiers are known, but served identities and model-call Steps are unavailable. Geometric visibility, software action checks and finite mechanical predictions establish different aspects of the apparatus; they do not certify physical repair. Factory service applicability, physical machining and fit, full service coverage, external contract identity and professional labor-time sources remain qualified. Earlier incomplete diagnostics and complete original-rule references stay separate from amended-rule model attempts. The larger comparative study remains pending.

- Before: Geometry is detailed but service access, component mapping and legal transitions are incomplete in the reviewed snapshot. Complete original-rule software references are available for the configured abnormal conditions; equivalent coverage under the amended rules remains to be demonstrated. Service thresholds and orientation information must be resolved rather than invented .
- After: Geometry is detailed but service access, component mapping and legal transitions are incomplete in the reviewed snapshot. Complete original-rule software references are available for the configured abnormal conditions; equivalent coverage under the amended rules remains to be demonstrated. Service thresholds and orientation information must be resolved rather than invented.

- Before: Mechanical models use generic material properties and finite comparisons. They support selected state estimates but are not selected-part durability validation. No operating-engine endpoint contributes to scoring .
- After: Mechanical models use generic material properties and finite comparisons. They support selected state estimates but are not selected-part durability validation. No operating-engine endpoint contributes to scoring.

- Before: Technician charges are a domain cost estimate rather than measured workshop performance. The historical action table lacks the required professional time sources and correction schedule; later scripted diagnostic charges remain analyst estimates. API-equivalent cost may be unavailable for a returned model; that limitation must not be concealed by a subscription-price proxy .
- After: Technician charges are a domain cost estimate rather than measured workshop performance. The historical action table lacks the required professional time sources and correction schedule; later scripted diagnostic charges remain analyst estimates. API-equivalent cost may be unavailable for a returned model; that limitation must not be concealed by a subscription-price proxy.


ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
