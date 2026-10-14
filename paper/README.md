# The report

**Evaluating AI Agents on a Head-Gasket Repair Procedure** · Joshua Pinckard · ToolsEnabled, Inc. · October 2026 · version 25

| File | What it is |
|---|---|
| `paper.pdf` | the report, 64 pages (body 1-14, appendices 15-64) |
| `paper.docx` | the same report as a Word document |
| `paper.txt` | plain-text extraction of the PDF |
| `figures/` | figure 1 (workflow, PNG/SVG/PDF), figure 2 (oil render), figure 3 (CAD isometric), figure 4 (joint laws) |
| `claim-to-data.csv` | the claim ledger: every number printed in the report bound to its source data (905 claims) |
| `CHANGES-v25.md` | every change from the audited v24 build, with before and after text |
| `LICENSE` | CC BY 4.0 for the report text and figures |

The benchmark asks an AI agent to replace a head gasket through a game
interface to a detailed CAD model of a real 1990s 1.6 L SOHC inline-four
engine. It follows [Engine Bench](https://toolsenabled.ai/bench/)
([code](https://github.com/ToolsEnabled/engine-bench)) and uses the same engine
model: Engine Bench asks an agent to build the engine; this benchmark asks it
to repair one. The environment, the scorer and the run records the report
describes are in this repository (`../env/`, `../scorer/`, `../runs/`).

**Three exploratory standard-job runs are reported, one each for GPT-6.1-Sol,
GPT-6-Astra and GPT-6-Luna run through Codex CLI.** No run completed the repair
fully correctly; the highest partial score was 41.7%. These are single runs:
they describe behaviour and do not rank the models. Served model identities,
model-call Steps and API-equivalent Cost are unavailable. GPT-6-Luna's final
response exceeded the collector's capture limit, so its final-turn token
coverage and agent wall time are unavailable. The larger comparative study
remains pending.

## Source locators in `claim-to-data.csv`

Each row of the ledger names the file a number was produced from
(`producer_path`), its SHA-256 (`member_sha256`), the packet inventory
(`inventory_sha256`) and a pointer into the file. Most producers are sealed
research packets that are not part of this repository. In this public copy
their locators are written as `sealed:<lane>/<packet>/<path>` (for example
`sealed:env/original-v4-95c3193/source.tar.gz`), and the benchmark policy documents as
`sealed:benchmark-policy/<document>`; the build used machine-local
shared-folder spellings of the same files. Locators that begin with
`current-paper-source/` or `data/` are relative to the report's own source
workspace. Only the locator column was rewritten: every hash, pointer and value
is as audited, and **the PDF, DOCX and TXT are unchanged**. The first part of
each sealed locator names the work area that owns the packet (`joint`,
`engine-rotating`, `engine-cad`, `env`, `sim-2`, `coordinator`,
`benchmark-policy`).

The report's own analysis toolchain and audit receipts stay in the sealed
research workspace. The numbers in Table 1 and Appendix F can be checked
against `../runs/reference/V1-amended/` and the scored summaries in
`../runs/exploratory/`; see `../REPRODUCIBILITY.md`.

## Licence and support

The report text and its figures (`paper.pdf`, `paper.docx`, `paper.txt` and
the figure files) are released under the Creative Commons Attribution 4.0
International licence (CC BY 4.0, see `LICENSE`). The benchmark code is
released under the MIT licence (`../LICENSE`). Service-source material cited in
the report keeps the terms of its publishers; a publicly accessible source is
not a statement that its complete text or geometry may be redistributed.

Questions, corrections and bug reports: open an issue on
ToolsEnabled/head-gasket-bench, or write to support@toolsenabled.ai.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
