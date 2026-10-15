# Head Gasket Bench 0.1.3

Patch release of the launcher (`env/headgasket/cli.py`). It stops one known
issue of the pinned environment from ending a run. Nothing else changes: the
pinned environment runtime (`env/hgj/`, `env/tools/source_server.py`, the
amended epoch), and so the environment epoch, the five configurations, the
removal policy, the scorer, the published records, the board and the paper are
the same as in 0.1.2 (`python3 -m headgasket pins --check`; `runs/SHA256SUMS`;
`python3 tools/build_board.py --check`). Every published record replays and
scores exactly as before.

## What was wrong

A `remove` that names a `route_id` that is not one of the routes of an installed
part that comes off on its own is refused by the pinned environment
(`REMOVAL_POLICY_REFUSED: unknown requested route`). The environment then scores
the refused call for CP02, and its scoring step fails on the unknown route
(`env/hgj/checkpoints.py`, `disassembly`, evaluating the call with
`env/hgj/removal_policy.py`, `evaluate_removal`). The failure is outside the
game's own error handling, so the server answers that call with a JSON-RPC error
(`-32602`, `Invalid request`), and every later call, `look` and `finish`
included, fails the same way, because each call scores the whole journal again.
The saved record keeps the calls made before the failing one. 0.1.2 listed this
as a known issue. A model run ToolsEnabled made on 2026-10-14 (not published)
stopped this way after 130 calls, at a `remove` of `ignition_wire_stay_bolt`
with route `outward-unthread` (its only route is `unthread`).

## What changed

`serve` answers such a call itself, before it reaches the pinned server, with a
refusal shaped like the environment's own (an MCP tool result with `isError`
true):

```json
{"ok":false,"refusal":"REMOVAL_POLICY_REFUSED: unknown requested route for part_id 'ignition_wire_stay_bolt'; its routes are 'unthread' (name one as route_id, or leave route_id out)","turns_remaining":894}
```

The launcher resolves the part as the environment does: its id or stock label,
and the removal-policy part it stands for, including a replacement fitted during
the run. It also answers any other form of the call that would stop the run,
such as the internal id of a fitted replacement, which the environment does not
accept as a part id but its scoring step reads as given: when `part_id` as given
names the current body of a removal-policy part and `route_id` is not one of that
part's routes, the launcher runs the pinned scoring step read-only on the record
so far, with the call added as a refused attempt, and answers only if that step
would fail. The game state is only read.

Calls the environment refuses without stopping reach it unchanged and are
recorded as before: a part it does not know, a `remove` without `route_id` (or
with `null`), and a route that is not the part's when the part is already off,
comes off only with its assembly or stays for the job.

**The refused call is not recorded.** It never reaches the pinned server, so it
is not in `run.json`, `actions.jsonl` or `report.json`: it uses no attempt
(`turns_remaining` is unchanged), is charged no technician seconds and is not
counted for CP02 or as a mistake. `serve` prints how many such calls it
answered when it stops. This is how 0.1.2 treats a call after the budget. The
pinned environment cannot record the call without failing, and a record holding
it could not be scored; without it, the record is an ordinary record of the calls
that reached the environment, so `replay`, `verify`, `validate`, the scorer and
`tools/validate_submission.py` accept it as they are.

## Runs made with an earlier launcher

A run made with the 0.1.2 launcher (or earlier, or with the pinned server started
some other way) that made such a call stopped there: its record ends with the
call before it, and the calls after it were answered with a JSON-RPC error and
not recorded. Such a record replays and scores as a run that stopped early, and
can be submitted as one. None of the 14 published records has such a call (each
of their 714 `remove` calls with a `route_id` names one of its part's routes).
Ten of the eleven exploratory runs on the board finished, which a run stopped this
way could not do; the eleventh, `gpt-6.1-sol`, ended without `finish`
when the model ended its turn (its `RESULT.md`).

## Checks

- `env/tests/test_headgasket_cli.py` `RouteTests`: the refusal, and `look` and
  `finish` working after it, with the record, replay, `verify` and `validate`;
  calls the environment refuses safely still reach it, and a call before the
  client is initialized still gets the server's error; the calls of
  `runs/family/V1-correct` with five such calls added (the one above, before that
  record's own `remove` of the same part with `unthread`, and calls naming the
  fitted gasket by stock label and by internal id) produce that record byte for
  byte; every `remove` with a `route_id` in the published records names one of
  its part's routes.
- Served through `serve` 0.1.3, the calls of each of the 13 records in
  `runs/family/` produce `run.json` and `actions.jsonl` byte for byte with no call
  answered by the launcher. The 130 calls of the run above, its failing call and
  the 12 calls it made after it up to `finish` give a finished record that
  replays exactly, verifies and passes `tools/validate_submission.py`.

## Still open (they need a new environment epoch)

The pinned environment itself still fails on such a call when it is started
without the launcher, and the other known issues listed in
`RELEASE-NOTES-0.1.2.md` are unchanged.
