# The twelve checkpoints

The primary score is twelve pass/fail checkpoints worth 18 points. They are
evaluated by `hgj/checkpoints.py` from the saved action journal and final
state; the definitions below are its `DEFINITIONS` table.

| ID | Points | Checkpoint |
|---|---:|---|
| CP01 | 1 | Service lookup before head tightening |
| CP02 | 2 | Valid disassembly |
| CP03 | 1 | TDC and aligned marks before belt removal |
| CP04 | 1 | Staged head loosening |
| CP05 | 1 | Mating surfaces cleaned before gasket placement |
| CP06 | 1 | Flatness measured before the correct service decision |
| CP07 | 1 | Bolts measured before the correct keep or replace decision |
| CP08 | 2 | Correct new gasket and aligned dowels |
| CP09 | 2 | Valid first torque stage |
| CP10 | 2 | Valid final torque stage |
| CP11 | 2 | Timing restored and checked |
| CP12 | 2 | Parts and attachments restored |

Formulas, as computed in `score.primary_score`:

- `points_earned` = sum of the weights of the checkpoints that passed.
- `S_full` = 1 if all twelve passed, else 0.
- `S_partial` = 0.5 × points_earned / 18 + 0.5 × S_full.

The checkpoint revision in every shipped configuration is
`amendment-1-20261009`. Under it two head-bolt loosening sequences are
accepted, 10 9 8 7 6 5 4 3 2 1 (exact reverse) and 10 9 8 7 6 3 4 5 2 1, as
long as one sequence is used for every loosening pass; and the valve-cover
gasket may be a new one or the original when it was inspected, found
serviceable and refitted with the specified oil and corner sealant.

Secondary measures, saved beside the checkpoints:

- `bolt_accuracy`: ten head bolts × six checks each (60 items).
- `checklist_accuracy`: the reference checklist for the variant, including the
  626 reinstallation positions and 100 attachment restorations of the removal
  policy.
- `mistakes`: typed incidents, for example `wrong_order`, `wrong_torque_value`,
  `missing_torque_stage`, `wrong_gasket`, `reused_stretched_bolt`,
  `timing_marks_off`, `missing_attachment_restore`.
- `human_time`: estimated technician seconds charged per attempt, split into
  productive and penalty seconds. Every duration is an analyst estimate from
  `data/labor-v2.json`; none is a measured flat rate.

What the score does not contain: there is no engine model, no joint or sealing
physics and no soak test in the loop. A perfect score means the recorded
procedure satisfied the written rules, not that a real engine would run.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
