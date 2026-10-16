# Round 2 — lead-only finish

Round 2 evidence date: October 15, 2026 (UTC).

The only two full repairs (18/18) in round 2 came from Fleet with one lead and four workers. Mean points out of 18: Fleet 1+4, 12.75; Fleet 1+2×2, 11.5; Codex native subagents, 7.5; single agent, 5.75.

Sixteen runs, four per setup, on one deterministic V1 task in Head Gasket Bench 0.1.3, with enforced lead-only finish. All runs requested gpt-6-luna at max reasoning effort through Codex CLI 0.162.1; requested model labels do not independently attest served weights. The benchmark environment and independent scorer agreed on all 16 round-2 scores.

**Four repetitions of one task cannot rank the arms.**

## Methods

The serial fixed order is S, N, FA, FB repeated four times; it is interleaved, not randomized.

S uses one agent; N uses native subagents with defaults; FA requests one lead plus four builders; FB requests one lead, two builders and two workers per builder.

Team size, delegation instructions, context packaging and tool surfaces differ together, so these configurations do not isolate the effect of transport.

Head Gasket Bench launcher 0.1.3, commit 837f15c6ade8462f83fe34b218784e3dd198a048, pinned V1 and unchanged independent scorer refit-preparation-20261010+cp02-20261014; Codex 0.162.1, requested gpt-6-luna effort max, default service tier. Fleet arms used Fleet MCP 1.9.0.

Each run shared one engine, a 1,024-attempt environment budget, a 1,024-forwarded-call hub cap, a three-hour agent cap, and at most five continuations after 120 seconds of quiet job tools. Agents can plan concurrently, but the shared engine receives one action at a time.

The hub now requires a single-use driver grant for each lead finish, based on the trusted app-server item event, socket parent PID/starttime, runtime call id, lead thread and argument hash.

Round 2 observed zero non-lead terminal closures and zero attempted unauthorized finishes in 16 runs. Zero observed unauthorized closures validates the observed operation of the guard; it does not by itself establish improved repair accuracy or a general underlying failure probability.

The launcher-0.1.2 S1 pilot and all plumbing smoke runs are excluded from the scored cohorts.

## All 16 scheduled runs

There are twelve binary checkpoints totaling 18 points. Environment points are primary. S_full = 1 only when all checkpoints pass; S_partial = 0.5 × points/18 + 0.5 × S_full.

| Run | Environment /18 | Independent /18 | S_full | Failed CP (environment) | Termination |
| --- | --- | --- | --- | --- | --- |
| R2-S1 | 1 | 1 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 | finished |
| R2-N1 | 1 | 1 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 | idle_no_continuations_left |
| R2-FA1 | 18 | 18 | 1 | none | finished |
| R2-FB1 | 14 | 14 | 0 | CP02, CP12 | finished |
| R2-S2 | 3 | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | finished |
| R2-N2 | 14 | 14 | 0 | CP02, CP12 | finished |
| R2-FA2 | 18 | 18 | 1 | none | finished |
| R2-FB2 | 13 | 13 | 0 | CP02, CP05, CP12 | finished |
| R2-S3 | 16 | 16 | 0 | CP12 | finished |
| R2-N3 | 1 | 1 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP11, CP12 | finished |
| R2-FA3 | 3 | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | finished |
| R2-FB3 | 3 | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | finished |
| R2-S4 | 3 | 3 | 0 | CP01, CP02, CP04, CP05, CP06, CP07, CP08, CP09, CP10, CP12 | finished |
| R2-N4 | 14 | 14 | 0 | CP02, CP12 | finished |
| R2-FA4 | 12 | 12 | 0 | CP02, CP04, CP07, CP12 | finished |
| R2-FB4 | 16 | 16 | 0 | CP12 | finished |

Launcher 0.1.3 can refuse invalid removal routes before recording, consuming no environment turn.

## Per-setup summaries and historical context

| Arm | R2 environment points mean [range] | R2 independent mean [range] | R1 environment mean [range] | R2 S_full | R2 wall s mean [range] | R2 rejected-finish runs |
| --- | --- | --- | --- | --- | --- | --- |
| S | 5.75 [1–16] | 5.75 [1–16] | 8.5 [3–14] | 0/4 | 655.004 [490.662–821.677] | 0/4 |
| N | 7.5 [1–14] | 7.5 [1–14] | 8.5 [3–14] | 0/4 | 1,697.925 [777.927–2,542.254] | 0/4 |
| FA | 12.75 [3–18] | 12.75 [3–18] | 8 [0–16] | 2/4 | 1,529.697 [969.714–1,857.893] | 0/4 |
| FB | 11.5 [3–16] | 11.5 [3–16] | 11.5 [9–14] | 0/4 | 1,930.996 [1,114.013–2,899.308] | 0/4 |

Ranges are observed extrema, not confidence intervals. Round 1 had no full repairs in eight runs; FB2 scored 9/18 in the environment and 8/18 with the independent scorer because of a CP07 disagreement. The rounds use different finish protocols and remain separate exploratory cohorts.

## Interpretation and availability

**Four repetitions of one task cannot rank the arms.** Team size, delegation instructions, context packaging and tool surfaces differ together, so these configurations do not isolate the effect of transport.

A full repair here means all twelve benchmark checkpoints passed; it does not establish physical repair competence. No per-arm cost-effectiveness or general speed claim is supported. Shared-account balance movements are not isolated per-run costs, and plan usage is not assigned a cash price.

Only tables, scores and methods are published here; agent transcripts and raw records remain private.

[Round 1](REPORT-R1.md) · [Study summary](README.md) · [Claim sources](CLAIMS.md)
