# Claim-to-source ledger

Scope: every new or changed public sentence, score row and chart label in this study, the repository README study note, and the Fleet / Head Gasket Bench website additions.

Source identifiers refer to retained private audit reports; raw records and transcripts are not published. Line numbers use the exact source bytes identified below. The public reports are edited extracts of scores and methods, not copies of the private reports.

| Source | SHA-256 |
| --- | --- |
| REPORT.md | `163d30371f1431d94590070622f0bd0b9f4e8f6ef183625b8d18d495dc815174` |
| REPORT-R2.md | `115691cccde2109491ef70740da7db79e487de77218f67a2bbd6f1f5c93d7d89` |
| REPORT-SITE.md | `5246d8e281176aa51960305aeb32e58816a8cf8bacb734748acec457dcaedcd8` |
| NEXT-RUNS.md | `46ed401445c8d051f524e44c69c9c94f47609f56d18e25dc19d80af937364ec5` |
| PUBLICATION-BRIEF.md | `b99f01fc7e15303fe1b06bb17b12e871b20fbf00df177e64b33a3963e2f2629f` |


| ID | Public text or table row | Source line(s) | Mapping |
| --- | --- | --- | --- |
| C001 | Two 18/18 repairs with Fleet 1+4. | REPORT-R2.md:L19, REPORT-R2.md:L23, REPORT-R2.md:L3 | 18/18 and S_full=1 in exactly these two of the sixteen rows. |
| C002 | The only two full repairs (18/18) in round 2 came from Fleet with one lead and four workers. | REPORT-R2.md:L19, REPORT-R2.md:L23, REPORT-R2.md:L7 | Complete sixteen-row score table; no other S_full=1. |
| C003 | Mean points out of 18: Fleet 1+4, 12.75; Fleet 1+2×2, 11.5; Codex native subagents, 7.5; single agent, 5.75. | REPORT-R2.md:L80, REPORT-R2.md:L81, REPORT-R2.md:L82, REPORT-R2.md:L83 |  |
| C004 | Sixteen runs, four per setup, on one deterministic V1 task in Head Gasket Bench 0.1.3, with enforced lead-only finish. | REPORT-R2.md:L3, REPORT-R2.md:L9, REPORT-R2.md:L144 |  |
| C005 | All runs requested gpt-6-luna at max reasoning effort through Codex CLI 0.162.1; requested model labels do not independently attest served weights. | REPORT-R2.md:L9 |  |
| C006 | The benchmark environment and independent scorer agreed on all 16 round-2 scores. | REPORT-R2.md:L17, REPORT-R2.md:L110 | All sixteen environment/independent score pairs and disagreement rows agree. |
| C007 | Four repetitions of one task cannot rank the arms. | REPORT-R2.md:L3 | Verbatim report sentence. |
| C008 | Team size, delegation instructions, context packaging and tool surfaces differ together, so these configurations do not isolate the effect of transport. | REPORT-R2.md:L7 | Verbatim report sentence. |
| C009 | Round 1 had no full repairs in eight runs; FB2 scored 9/18 in the environment and 8/18 with the independent scorer because of a CP07 disagreement. | REPORT.md:L3, REPORT.md:L210 |  |
| C010 | The rounds use different finish protocols and remain separate exploratory cohorts. | REPORT-R2.md:L85 |  |
| C011 | A full repair here means all twelve benchmark checkpoints passed; it does not establish physical repair competence. | REPORT.md:L55, REPORT.md:L224 |  |
| C012 | Only tables, scores and methods are published here; agent transcripts and raw records remain private. | REPORT-SITE.md:L39 | PUBLICATION-BRIEF.md:L17, PUBLICATION-BRIEF.md:L18
| C013 | The serial fixed order is S, N, FA, FB repeated four times; it is interleaved, not randomized. | REPORT-R2.md:L7 | Verbatim report sentence. |
| C014 | S uses one agent; N uses native subagents with defaults; FA requests one lead plus four builders; FB requests one lead, two builders and two workers per builder. | REPORT-R2.md:L7 | Verbatim report sentence; Fleet 1+2×2 therefore denotes seven agents, not five. |
| C015 | Head Gasket Bench launcher 0.1.3, commit 837f15c6ade8462f83fe34b218784e3dd198a048, pinned V1 and unchanged independent scorer refit-preparation-20261010+cp02-20261014; Codex 0.162.1, requested gpt-6-luna effort max, default service tier. | REPORT-R2.md:L9 | Verbatim wording with Markdown code delimiters removed. |
| C016 | Fleet arms used Fleet MCP 1.9.0. | REPORT.md:L15, REPORT-R2.md:L9 |  |
| C017 | Each run shared one engine, a 1,024-attempt environment budget, a 1,024-forwarded-call hub cap, a three-hour agent cap, and at most five continuations after 120 seconds of quiet job tools. | REPORT.md:L22, REPORT.md:L41, REPORT-R2.md:L9 |  |
| C018 | Agents can plan concurrently, but the shared engine receives one action at a time. | REPORT.md:L47 | Verbatim report sentence. |
| C019 | The hub now requires a single-use driver grant for each lead finish, based on the trusted app-server item event, socket parent PID/starttime, runtime call id, lead thread and argument hash. | REPORT-R2.md:L11 | Verbatim report sentence; this describes the study harness, not a shipped Fleet feature. |
| C020 | Round 2 observed zero non-lead terminal closures and zero attempted unauthorized finishes in 16 runs. | REPORT-R2.md:L89 |  |
| C021 | Zero observed unauthorized closures validates the observed operation of the guard; it does not by itself establish improved repair accuracy or a general underlying failure probability. | REPORT-R2.md:L89 | Verbatim report sentence. |
| C022 | There are twelve binary checkpoints totaling 18 points. | REPORT.md:L55 | Verbatim report sentence. |
| C023 | Environment points are primary. | REPORT-R2.md:L34 | Verbatim report sentence. |
| C024 | S_full = 1 only when all checkpoints pass; S_partial = 0.5 × points/18 + 0.5 × S_full. | REPORT.md:L55, REPORT-R2.md:L34 |  |
| C025 | Launcher 0.1.3 can refuse invalid removal routes before recording, consuming no environment turn. | REPORT-R2.md:L74 | Verbatim report sentence. |
| C026 | Ranges are observed extrema, not confidence intervals. | REPORT-R2.md:L85 | Verbatim report sentence. |
| C027 | No per-arm cost-effectiveness or general speed claim is supported. | REPORT-R2.md:L140 | Verbatim report sentence. |
| C028 | Shared-account balance movements are not isolated per-run costs, and plan usage is not assigned a cash price. | REPORT-R2.md:L140 |  |
| C029 | The launcher-0.1.2 S1 pilot and all plumbing smoke runs are excluded from the scored cohorts. | REPORT.md:L245, REPORT.md:L247, REPORT-R2.md:L9 |  |
| C030 | Round 1 ran serially in the order S1R, FA1, N1, FB1, FB2, N2, FA2, S2, with two runs per setup. | REPORT.md:L22, REPORT.md:L3 |  |
| C031 | Round 1 instructed the lead to finish but did not enforce finish ownership in the hub; FA2 ended when a read-only worker called finish and scored 0/18. | REPORT.md:L49, REPORT.md:L5, REPORT.md:L188 |  |
| C032 | For FB2, the environment accepted bolt measurements and reuse decisions for CP07 without a first tightening stage; the independent scorer required that stage and failed CP07. | REPORT.md:L210 |  |
| C033 | Two runs per arm cannot rank the arms, establish superiority/equivalence, estimate stable failure probabilities, or support general cost or speed claims. | REPORT.md:L224 | Verbatim report sentence. |
| C034 | Round 2 evidence date: October 15, 2026 (UTC). | REPORT-R2.md:L3 |  |
| C035 | Round 1 evidence date: October 14, 2026 (PDT), October 15, 2026 (UTC). | REPORT.md:L3 |  |
| C036 | \| Run \| Environment /18 \| Independent /18 \| S_full \| Failed CP (environment) \| Termination \| | REPORT-R2.md:L15 | Exact table row; private links removed. |
| C037 | \| R2-S1 \| 1 \| 1 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 \| finished \| | REPORT-R2.md:L17 | Exact table row; private links removed. |
| C038 | \| R2-N1 \| 1 \| 1 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 \| idle_no_continuations_left \| | REPORT-R2.md:L18 | Exact table row; private links removed. |
| C039 | \| R2-FA1 \| 18 \| 18 \| 1 \| none \| finished \| | REPORT-R2.md:L19 | Exact table row; private links removed. |
| C040 | \| R2-FB1 \| 14 \| 14 \| 0 \| CP02, CP12 \| finished \| | REPORT-R2.md:L20 | Exact table row; private links removed. |
| C041 | \| R2-S2 \| 3 \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| finished \| | REPORT-R2.md:L21 | Exact table row; private links removed. |
| C042 | \| R2-N2 \| 14 \| 14 \| 0 \| CP02, CP12 \| finished \| | REPORT-R2.md:L22 | Exact table row; private links removed. |
| C043 | \| R2-FA2 \| 18 \| 18 \| 1 \| none \| finished \| | REPORT-R2.md:L23 | Exact table row; private links removed. |
| C044 | \| R2-FB2 \| 13 \| 13 \| 0 \| CP02, CP05, CP12 \| finished \| | REPORT-R2.md:L24 | Exact table row; private links removed. |
| C045 | \| R2-S3 \| 16 \| 16 \| 0 \| CP12 \| finished \| | REPORT-R2.md:L25 | Exact table row; private links removed. |
| C046 | \| R2-N3 \| 1 \| 1 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 \| finished \| | REPORT-R2.md:L26 | Exact table row; private links removed. |
| C047 | \| R2-FA3 \| 3 \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| finished \| | REPORT-R2.md:L27 | Exact table row; private links removed. |
| C048 | \| R2-FB3 \| 3 \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| finished \| | REPORT-R2.md:L28 | Exact table row; private links removed. |
| C049 | \| R2-S4 \| 3 \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| finished \| | REPORT-R2.md:L29 | Exact table row; private links removed. |
| C050 | \| R2-N4 \| 14 \| 14 \| 0 \| CP02, CP12 \| finished \| | REPORT-R2.md:L30 | Exact table row; private links removed. |
| C051 | \| R2-FA4 \| 12 \| 12 \| 0 \| CP02, CP04, CP07, CP12 \| finished \| | REPORT-R2.md:L31 | Exact table row; private links removed. |
| C052 | \| R2-FB4 \| 16 \| 16 \| 0 \| CP12 \| finished \| | REPORT-R2.md:L32 | Exact table row; private links removed. |
| C053 | \| Arm \| R2 environment points mean [range] \| R2 independent mean [range] \| R1 environment mean [range] \| R2 S_full \| R2 wall s mean [range] \| R2 rejected-finish runs \| | REPORT-R2.md:L78 | Exact table row; private links removed. |
| C054 | \| S \| 5.75 [1–16] \| 5.75 [1–16] \| 8.5 [3–14] \| 0/4 \| 655.004 [490.662–821.677] \| 0/4 \| | REPORT-R2.md:L80 | Exact table row; private links removed. |
| C055 | \| N \| 7.5 [1–14] \| 7.5 [1–14] \| 8.5 [3–14] \| 0/4 \| 1,697.925 [777.927–2,542.254] \| 0/4 \| | REPORT-R2.md:L81 | Exact table row; private links removed. |
| C056 | \| FA \| 12.75 [3–18] \| 12.75 [3–18] \| 8 [0–16] \| 2/4 \| 1,529.697 [969.714–1,857.893] \| 0/4 \| | REPORT-R2.md:L82 | Exact table row; private links removed. |
| C057 | \| FB \| 11.5 [3–16] \| 11.5 [3–16] \| 11.5 [9–14] \| 0/4 \| 1,930.996 [1,114.013–2,899.308] \| 0/4 \| | REPORT-R2.md:L83 | Exact table row; private links removed. |
| C058 | \| Run \| Points /18 \| S_full \| Failed checkpoints (environment) \| Independent /18 \| | REPORT.md:L63 | Exact table row; private links removed. |
| C059 | \| S1R \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| 3 \| | REPORT.md:L65 | Exact table row; private links removed. |
| C060 | \| S2 \| 14 \| 0 \| CP02, CP12 \| 14 \| | REPORT.md:L66 | Exact table row; private links removed. |
| C061 | \| N1 \| 14 \| 0 \| CP02, CP12 \| 14 \| | REPORT.md:L67 | Exact table row; private links removed. |
| C062 | \| N2 \| 3 \| 0 \| CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 \| 3 \| | REPORT.md:L68 | Exact table row; private links removed. |
| C063 | \| FA1 \| 16 \| 0 \| CP12 \| 16 \| | REPORT.md:L69 | Exact table row; private links removed. |
| C064 | \| FA2 \| 0 \| 0 \| CP01, CP02, CP03, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 \| 0 \| | REPORT.md:L70 | Exact table row; private links removed. |
| C065 | \| FB1 \| 14 \| 0 \| CP02, CP12 \| 14 \| | REPORT.md:L71 | Exact table row; private links removed. |
| C066 | \| FB2 \| 9 \| 0 \| CP01, CP02, CP09, CP10, CP12 \| 8 (CP07 also fails) \| | REPORT.md:L72 | Exact table row; private links removed. |
| C067 | \| S \| 8.5 [3–14] \| 8.5 [3–14] \| | REPORT.md:L123 | First three columns of the source table. |
| C068 | \| N \| 8.5 [3–14] \| 8.5 [3–14] \| | REPORT.md:L124 | First three columns of the source table. |
| C069 | \| FA \| 8 [0–16] \| 8 [0–16] \| | REPORT.md:L125 | First three columns of the source table. |
| C070 | \| FB \| 11.5 [9–14] \| 11 [8–14] \| | REPORT.md:L126 | First three columns of the source table. |
| C071 | Fleet 1+4 — mean 12.75/18; scores 18, 18, 3, 12; full repairs 2/4. | REPORT-R2.md:L82, REPORT-R2.md:L7 | Chart labels and values reproduce all four matching run rows; width = mean / 18. |
| C072 | Fleet 1+2×2 — mean 11.5/18; scores 14, 13, 3, 16; full repairs 0/4. | REPORT-R2.md:L83, REPORT-R2.md:L7 | Chart labels and values reproduce all four matching run rows; width = mean / 18. |
| C073 | Codex native subagents — mean 7.5/18; scores 1, 14, 1, 14; full repairs 0/4. | REPORT-R2.md:L81, REPORT-R2.md:L7 | Chart labels and values reproduce all four matching run rows; width = mean / 18. |
| C074 | Single agent — mean 5.75/18; scores 1, 3, 16, 3; full repairs 0/4. | REPORT-R2.md:L80, REPORT-R2.md:L7 | Chart labels and values reproduce all four matching run rows; width = mean / 18. |
| C-LABELS | Headings, report links, chart captions, setup labels, score labels, dates, Study results / See the 18/18 study results / View the results chart on Fleet, and Earlier results labels. | REPORT-R2.md:L3, REPORT-R2.md:L7, REPORT.md:L3 | Navigation/structure; links checked against the published file inventory. Earlier-results edits scope existing claims to the cohorts already described. |
| C-EARLIER | In these pre-study runs, no agent completed the job correctly. The highest agent score in this earlier cohort was 16 of 18 points, by claude-opus-5-5 at effort max, in 5 of 5 finished runs. Site: 16 of 18 points in the earlier release-0.1.2 cohort. | REPORT.md:L206 | Existing repository README at 837f15c6, lines 64–85, and original website headgasket page at 3a807299, line 198. Only time scope changed; historical paper quotation retained verbatim. |
