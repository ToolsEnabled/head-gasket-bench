# The twelve checkpoints

The Head Gasket Job benchmark asks an agent to replace the head gasket on a
real 1990s 1.6 L SOHC inline-four in a deterministic procedure game (nothing
physical is simulated), through a tool interface. The scorer never watches the agent work. It reads the saved run
record afterwards (configuration, initial state, every tool call with its
result, and the final state) and decides twelve yes-or-no questions. Each
question has a weight; the weights add up to 18 points.

| ID | Weight | Kind | Question the scorer answers |
|---|---:|---|---|
| CP01 | 1 | process | Were the torque values, both torque stages and the tightening sequence looked up in the service information before the first head bolt was tightened? |
| CP02 | 2 | process | Was the disassembly valid under the removal policy: no attempt to remove a part that was still blocked by, or still attached to, something else, and no refused removal attempt? |
| CP03 | 1 | process | Before the timing belt came off, was cylinder 1 at top dead centre with the timing marks aligned, confirmed by a timing check? |
| CP04 | 1 | process | Were the head bolts loosened in a documented order and in the documented stages before the head was removed? |
| CP05 | 1 | final state | After the head and the old gasket were removed, and before the new gasket was placed, were both mating surfaces cleaned, and are they clean in the final state? |
| CP06 | 1 | process + final state | Were head and block flatness both measured and compared with the service limit before the head went back on, and was the decision right for this engine (machine or replace a warped head; otherwise reuse it)? |
| CP07 | 1 | process + final state | Was every head bolt measured against the reuse limit before it was kept or replaced, and was each decision right (replace a stretched bolt; otherwise keep)? |
| CP08 | 2 | final state | Is a new head gasket of the correct specification (75 mm bore, 0.762 mm compressed thickness, multilayer steel) installed in the correct orientation on aligned dowels? Installing the wrong part that is also on the shelf fails. |
| CP09 | 2 | final state | Do all ten head bolts carry a valid stage-1 torque at the specified value, applied in the specified sequence? |
| CP10 | 2 | final state | Do all ten head bolts carry a valid final-stage torque at the specified value, applied in the specified sequence after stage 1? |
| CP11 | 2 | final state | Is the timing restored: belt fitted and tensioned, marks aligned, confirmed by a successful timing check after the belt went back on? A worn belt must have been replaced. |
| CP12 | 2 | final state | Is reassembly complete: every removed part and every released fastener or attachment restored, or properly superseded by its replacement? The head gasket must be new; the valve-cover gasket must be new or the inspected, serviceable original refitted with sealant. |

A checkpoint passes only when every one of its requirements is observed in
the record. Missing evidence never earns a point: a tool call that succeeded
but produced no observation does not count as an observation. The JSON report
lists, for every checkpoint, each requirement, whether it was met, and the
sequence numbers of the tool calls that were used as evidence.

## Process checkpoints and final-state checkpoints

**Final-state checkpoints are judged on the final state**, in the same way
TheAgentCompany judges its checkpoints. If the agent does something wrong and
later corrects it fully (for example loosens a wrongly torqued bolt and redoes
both stages in order), the checkpoint can still pass. The wrong work and the
correction are still charged as mistakes and penalty time (below).

**Process checkpoints are judged on the order of events.** CP02, CP03 and
CP04, and the measure-before-decide part of CP06 and CP07, look at when things
happened. A violation fails the checkpoint even if the final state looks right:
a flatness measurement taken after the head was already reinstalled does not
satisfy CP06.

**Torque credit is cleared** whenever a bolt is loosened, removed or
reinstalled. CP09 and CP10 look at the stages applied to the bolt in its
current installation; stages applied before a removal do not carry over.

## The two accepted loosening orders (CP04)

The service information documents two complete loosening orders for the ten
head bolts, numbered by their position in the tightening sequence:

1. the loosening diagram printed in the service manual: 10, 9, 8, 7, 6, 3, 4, 5, 2, 1;
2. the exact reverse of the tightening sequence: 10, 9, 8, 7, 6, 5, 4, 3, 2, 1.

Under the current rule (revision `amendment-2-20261010`) either order passes,
but the agent must use **one** of them **consistently in every loosening
pass**. The reference supplies the number of passes and the angle increment of
each pass. Mixing the two orders, or switching order between passes, fails
CP04. Two earlier revisions remain selectable so that historical records can
be reproduced: `signoff-20261009` (the original rule: exactly the reference
sequence) and `amendment-1-20261009` (withdrawn: each pass could choose either
order independently). The revision is selected on the command line, never by
the record.

## The valve-cover gasket (CP12)

A new head gasket is mandatory. For the valve-cover gasket the service
information describes inspection, reuse when serviceable, and sealant at the
camshaft-holder corners. CP12 therefore accepts either a new valve-cover
gasket or the original one, inspected after removal and found serviceable,
refitted with sealant in the same service cycle. (The original rule required
both gaskets to be new; that was a benchmark policy, not a manual
requirement, and was withdrawn.)

## Variants

The reference family covers five variants of the same engine. V1 is the
baseline. V2 has one stretched head bolt that must be replaced (CP07). V3 has
a warped head that must be machined or replaced (CP06; both routes are
scripted). V4 has a wrong gasket on the shelf next to the right one (CP08). V5
has a worn timing belt that must be replaced (CP11). Seven scripted faulty
jobs show that each fault fails exactly the expected checkpoints; see
`SCORING.md`.

## Time charges: what they are and are not

Besides the points, the scorer reports **technician time** in seconds. Every
tool call is charged the time a technician would be estimated to spend on
that action, taken from the labour policy embedded in the record
(`human_time_policy`, with its source identifiers). Correct work is
**productive** time; executed wrong work and its redo are **penalty** time.
Mistakes are typed: blocked removal attempt, invalid action, redo, wrong
order, wrong torque value, missing torque stage, wrong gasket, wrong
orientation, reused stretched bolt, timing marks off, missing attachment
restoration, wrong part, wrong service decision, and others named in the
JSON. A correct redo does not erase an earlier mistake or its charge.

These figures are **analyst estimates**. They are not measured repair time,
not a published labour-time standard, and they never change the points or
the scores. If a required penalty has no price in the policy, the total is
reported as unknown rather than guessed.

Agent wall time, model calls, tokens and API-equivalent cost are **not**
derived from the record. They need separate receipts and are reported as
"unknown" when absent; the scorer's own running time is never substituted
for agent wall time.

## The 1,024-attempt budget

A run may make at most 1,024 tool-call attempts (refused calls count). The
scripted correct jobs use 436 to 440. A run that reaches the budget is scored
on its final state and reported as incomplete with the reason. The pinned
environment server still records a call made after the budget is spent (as a
refused attempt), and this scorer refuses a record of more than 1,024 attempts
(`record-domain`), so an agent should stop calling tools when `turns_remaining`
reaches 0. The launcher (`headgasket serve`, release 0.1.2 and later) answers
such a call itself without recording it, so its records stop at 1,024. A run that
stops early is scored as it stands: a partial record earns the points its
evidence supports, and a successful `finish` call is separate from passing
every checkpoint. A successful action recorded after a committed finish is
refused as contradictory to the environment's terminal-state contract.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
