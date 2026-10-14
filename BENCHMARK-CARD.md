# Head-gasket repair benchmark card

ToolsEnabled, Inc. · October 2026

This card adapts the topic structure of
[Datasheets for Datasets](https://arxiv.org/html/1803.09010v8) to an interactive
benchmark with source data, executable environments and run records.

## Motivation

The benchmark studies whether agents can complete a detailed mechanical repair
through tools. Work includes instruction lookup, planning, inspection, replacement,
ordered tightening and verification. ToolsEnabled, Inc. develops the environment
and authors the report. TheAgentCompany supplies the adopted aggregate completion
formulas; the repair environment and deterministic checkpoints are
application-specific. The intended contribution is a new application of existing
evaluation methods. The benchmark follows Engine Bench and uses the same engine
model, a real 1990s 1.6 L SOHC inline-four: Engine Bench asks an agent to build
the engine; this benchmark asks it to repair one.

## Composition

Five variants cover standard gasket replacement, a stretched head bolt, excessive
head flatness, a wrong gasket offered beside the correct replacement, and a worn
timing belt. Twelve weighted checkpoints sum to eighteen points. Per-bolt criteria,
typed mistakes and technician charges supplement the primary score. Geometry,
service-source material, policy specifications, interfaces, configurations, action
journals and evaluator reports are separate artifacts.

Public-source specifications are distinguished from benchmark policy. Conflicting
sources remain documented beside the selected interpretation. Agreement between
software evaluators does not resolve a service-source disagreement. The factory
grouped rocker path and a more extensive disassembly path need their own restoration
checks. CAD illustrations and software replay do not establish safe physical access.

Saved scripted cases include incomplete historical diagnostics, complete
original-rule references for the configured primary variants, and the amended-rule
complete standard-job trace that the report's Table 1 prints as the scripted
reference (18 of 18 points, 13,630 productive seconds, no penalty). Their
configurations, evaluators and rules define separate groups. Primary outcomes and
shared bolt/time fields agree between evaluators; complete checklists differ, and
external contract identity remains unauthenticated. Original-rule references do not
demonstrate the amended alternatives. They are not sampled model attempts, measured
technician work or evidence of an agent failure distribution.

Three exploratory standard-job runs are reported, one each for GPT-6.1-Sol,
GPT-6-Astra and GPT-6-Luna through Codex CLI. GPT-6.1-Sol stopped without finish and
scored 8.3%; GPT-6-Astra submitted finish, scored 41.7% and failed two process
checkpoints; GPT-6-Luna reached finish, scored 36.1% and failed disassembly, cleaning
and restoration checks, and its accepted game endpoint does not establish a
completed model turn. None achieved full checkpoint success. These are single runs:
they describe behaviour and do not rank the models. Served identity, model-call
Steps and API-equivalent price remain unavailable; recorded token counters and agent
wall intervals are retained. GPT-6-Luna's counters cover the observed prefix only; its
final-turn coverage and wall time are unavailable. The larger comparison remains
pending.

## Collection process

A model attempt starts from an identified configuration and uses the advertised
tools. Its collector must retain prompts, observed model identity, model-call/token
telemetry, tool attempts, the journal, termination reason and both evaluators'
reports. Failed, interrupted, incomplete and refused attempts remain recorded.
Submission of a finished job is distinct from correct work.

Amendment 1 accepts either documented head-bolt loosening order; Amendment 2 requires
one chosen order consistently across all passes. The cover-gasket amendment permits an
inspected serviceable valve-cover gasket to be refitted with sealant. A new head
gasket remains mandatory. Previous runs keep their original rules; a changed
runtime/rule combination requires its own run and verification.

The paper work analyzes saved artifacts. It does not collect new model attempts or
measure technician labor. Human-time charges, including typed mistake penalties,
are estimates with stated provenance, not a collected human comparison group.

## Processing and validation

Selected sources have original content hashes. Declared public display views retain
separate original and transformed hashes; they are never claimed byte-identical to
the original. Numeric statements, figures and report fields link to supporting data
through `claim-to-data.csv`.

Analysis checks checkpoint arithmetic, named bolt criteria, mistakes and charge
ledgers. Scripted and real cohorts remain separate. Missing model calls, tokens,
prices or wall times stay unavailable. Complete and available-case means have
explicit denominators. For eligible real runs, the run is the statistical unit;
variant allocation and resampling settings are specified before collection. Bolts
and checkpoints within a run are not treated as independent trials.

Replay and independent-evaluator agreement are software checks. They do not prove
factory applicability, dimensional accuracy, physical safety or the validity of
labor estimates. A soak or full engine-running simulation is not scored.

## Intended uses and limitations

Appropriate uses include research on long procedures, tool use, service lookup,
ordered execution, recovery from mistakes and reproducible evaluation. Comparisons
must disclose task, service-policy, runtime, evaluator, variant allocation and budget.

This benchmark does not certify technicians or vehicles, prescribe an actual repair,
estimate commercial quotations or establish physical safety. Scripted faulty jobs
cannot establish agent failure patterns. Missing model identity or price data cannot
be replaced by presumed model names, tool counts or subscription expenditure.

## Distribution and licence

The report (`paper.pdf`, 64 pages, with `paper.docx` and `paper.txt`) and its
authored figures are released under the Creative Commons Attribution 4.0
International licence (CC BY 4.0). The benchmark code (the environment, the
independent scorer and the tools in this repository) and the run data are
released under the MIT licence. These grants cover the report text, figures and code
only. Service-source material keeps the terms of its publishers: a publicly
accessible source is not a statement that its complete text or geometry may be
redistributed, and the report cites such material with explicit provenance rather
than reproducing it. Account identifiers and private host paths are excluded from
the public view. Historical artifacts and repository history have separate
disclosure scopes; the release excludes repository history.

Support channel: issues on the GitHub repository ToolsEnabled/head-gasket-bench,
and support@toolsenabled.ai.

## Maintenance

ToolsEnabled, Inc. versions task rules, runtime, variants, service policy,
evaluator, charge model and collector separately and retains their exact combination
for each run. Changes require new checks and distinct result groups. Original run
inputs remain immutable. Documentation corrections identify the affected version
and evidence; corrections to this release are tracked through the support channel
above. Open empirical limitations remain visible in the paper and each result
group's missing-value and qualification fields. The supported runtime for new
collection is `env/` in this repository; agent traces of the exploratory runs
are not published, only their scored results.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
