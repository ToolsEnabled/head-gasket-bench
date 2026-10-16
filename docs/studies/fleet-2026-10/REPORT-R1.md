# Round 1 — historical context

Round 1 evidence date: October 14, 2026 (PDT), October 15, 2026 (UTC).

Round 1 had no full repairs in eight runs; FB2 scored 9/18 in the environment and 8/18 with the independent scorer because of a CP07 disagreement.

## Methods

Round 1 ran serially in the order S1R, FA1, N1, FB1, FB2, N2, FA2, S2, with two runs per setup.

S uses one agent; N uses native subagents with defaults; FA requests one lead plus four builders; FB requests one lead, two builders and two workers per builder.

Head Gasket Bench launcher 0.1.3, commit 837f15c6ade8462f83fe34b218784e3dd198a048, pinned V1 and unchanged independent scorer refit-preparation-20261010+cp02-20261014; Codex 0.162.1, requested gpt-6-luna effort max, default service tier. Fleet arms used Fleet MCP 1.9.0.

Each run shared one engine, a 1,024-attempt environment budget, a 1,024-forwarded-call hub cap, a three-hour agent cap, and at most five continuations after 120 seconds of quiet job tools. Agents can plan concurrently, but the shared engine receives one action at a time.

Round 1 instructed the lead to finish but did not enforce finish ownership in the hub; FA2 ended when a read-only worker called finish and scored 0/18.

The launcher-0.1.2 S1 pilot and all plumbing smoke runs are excluded from the scored cohorts.

## All eight scored runs

There are twelve binary checkpoints totaling 18 points. Environment points are primary. S_full = 1 only when all checkpoints pass; S_partial = 0.5 × points/18 + 0.5 × S_full.

| Run | Points /18 | S_full | Failed checkpoints (environment) | Independent /18 |
| --- | --- | --- | --- | --- |
| S1R | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | 3 |
| S2 | 14 | 0 | CP02, CP12 | 14 |
| N1 | 14 | 0 | CP02, CP12 | 14 |
| N2 | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | 3 |
| FA1 | 16 | 0 | CP12 | 16 |
| FA2 | 0 | 0 | CP01, CP02, CP03, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 | 0 |
| FB1 | 14 | 0 | CP02, CP12 | 14 |
| FB2 | 9 | 0 | CP01, CP02, CP09, CP10, CP12 | 8 (CP07 also fails) |

| Arm | Environment mean [range] /18 | Independent mean [range] /18 |
| --- | --- | --- |
| S | 8.5 [3–14] | 8.5 [3–14] |
| N | 8.5 [3–14] | 8.5 [3–14] |
| FA | 8 [0–16] | 8 [0–16] |
| FB | 11.5 [9–14] | 11 [8–14] |

Ranges are observed extrema, not confidence intervals.

## Scorer disagreement and limits

For FB2, the environment accepted bolt measurements and reuse decisions for CP07 without a first tightening stage; the independent scorer required that stage and failed CP07.

**Two runs per arm cannot rank the arms, establish superiority/equivalence, estimate stable failure probabilities, or support general cost or speed claims.** Team size, delegation instructions, context packaging and tool surfaces differ together, so these configurations do not isolate the effect of transport. The rounds use different finish protocols and remain separate exploratory cohorts.

A full repair here means all twelve benchmark checkpoints passed; it does not establish physical repair competence. No per-arm cost-effectiveness or general speed claim is supported.

Only tables, scores and methods are published here; agent transcripts and raw records remain private.

[Round 2](REPORT-R2.md) · [Study summary](README.md) · [Claim sources](CLAIMS.md)
