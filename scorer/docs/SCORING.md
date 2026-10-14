# Scoring

## Formulas

The twelve checkpoints in `CHECKPOINTS.md` are binary. With the weights
w_i (1 or 2, summing to 18) and the outcomes c_i (1 pass, 0 fail):

```text
points     = sum_i w_i * c_i                     (0 to 18)
S_full     = 1 if every checkpoint passes, else 0
S_partial  = 0.5 * (points / 18) + 0.5 * S_full
```

S_full and S_partial follow TheAgentCompany: Frank F. Xu et al.,
"TheAgentCompany: Benchmarking LLM Agents on Consequential Real World Tasks",
arXiv:2412.14161 (2024), which scores a task as fully completed (S_full) and
otherwise gives partial credit for the fraction of checkpoints passed with the
same 0.5 / 0.5 split. The denominator is fixed at 18 in
`job_accuracy/checkpoints.py::weighted_score`; the function refuses any
checkpoint list that is not exactly the declared twelve with their declared
weights.

A correct job therefore scores 18 points, S_full = 1, S_partial = 1. Some
values a faulty job can reach:

| Points | Failed checkpoints (example) | S_full | S_partial |
|---:|---|---:|---:|
| 16 | CP10 | 0 | 0.444444 |
| 15 | CP07 + CP12 | 0 | 0.416667 |
| 14 | CP09 + CP10 | 0 | 0.388889 |
| 3 | all but CP01, CP02 | 0 | 0.083333 |

## What the scripted family shows

The thirteen scripted jobs of the reference family, scored under revision
`amendment-2-20261010`:

| Job | Points | S_full | S_partial | Checkpoints not met | Technician s (productive / penalty) |
|---|---:|---:|---:|---|---|
| V1-correct | 18 | 1 | 1 | none | 13630 / 0 |
| V2-correct | 18 | 1 | 1 | none | 13720 / 0 |
| V3-correct | 18 | 1 | 1 | none | 14950 / 0 |
| V4-correct | 18 | 1 | 1 | none | 13780 / 0 |
| V5-correct | 18 | 1 | 1 | none | 13720 / 0 |
| V3-correct-replacement-head | 18 | 1 | 1 | none | 13780 / 0 |
| V1-wrong_torque_sequence | 14 | 0 | 0.388889 | CP09, CP10 | 13390 / 840 |
| V1-under_torque | 16 | 0 | 0.444444 | CP10 | 13510 / 240 |
| V1-skipped_final_stage | 16 | 0 | 0.444444 | CP10 | 13510 / 12 |
| V4-wrong_gasket | 14 | 0 | 0.388889 | CP08, CP12 | 13750 / 60 |
| V2-reused_stretched_bolt | 15 | 0 | 0.416667 | CP07, CP12 | 13660 / 60 |
| V1-wrong_timing | 16 | 0 | 0.444444 | CP11 | 13600 / 150 |
| V1-missing_attachment_restoration | 16 | 0 | 0.444444 | CP12 | 10630 / 30 |

The scorer's results agree with the score the environment embedded in each
record on every checkpoint and on every shared bolt, mistake and time field.
That agreement is consistency between two implementations written against the
same signed checkpoint contract; it is not independent validation of the
contract itself.

## Secondary measures

The report also carries measures that are **not** part of the score:

* six raw criteria per head bolt (condition, stage-1 value, final value,
  stage-1 sequence rank, final sequence rank, stage order), 60 in all;
* a checklist of final-state items (part locations, fastener torques, surface
  condition, timing); an item whose condition was never observed is reported
  as unknown, not as wrong, so an overall checklist percentage is often
  unknown;
* technician time and typed mistakes (see `CHECKPOINTS.md`);
* tool-call counts (attempted, successful, refused).

The scorer compares its own primary result with the environment's embedded
score field by field (checkpoint outcomes, weights, points, S_full, S_partial)
and reports agreement or the exact disagreements. The embedded score is used
only for that comparison, never as an input to the independent result.

## The optional joint estimate is not part of scoring

The environment can attach an optional static estimate of the clamped joint
(bolt preload and gasket contact) to a saved record. It is a labelled,
non-scoring supplement: no checkpoint, point, time charge or mistake depends
on it, and the physics behind it was never validated for scoring. The
receiver for that supplement is **not shipped** in this package. The twelve
checkpoints, the technician-time estimate and the mistakes are computed
without it.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
