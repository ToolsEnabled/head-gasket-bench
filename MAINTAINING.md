# Maintaining the repository

The pull-request check (`.github/workflows/validate.yml`) reports; it does not
merge or refuse anything by itself. What protects `main` is a set of GitHub
settings that live outside the repository, so no file or test here can show
that they are in place. The owner makes them once; maintainers follow the review
steps below for every pull request.

## Settings the owner makes on GitHub

1. **A branch ruleset for `main`:**
   - require a pull request before merging, with at least one approving review,
     and dismiss approvals when new commits are pushed;
   - require the status check **`verdict`** (a job of the `validate`
     workflow). It runs on every pull request and fails unless the scope check
     passed and, for a submission pull request, the board check and every
     listed submission passed. Do not require the `submission (...)` jobs alone:
     a skipped job counts as passed, and when the scope check fails those jobs
     are skipped. (The workflow has no paths filter, so the check is never left
     pending on a pull request it skipped.)
   - require branches to be up to date before merging, so the check ran
     against the current `main`;
   - block force pushes and deletions of `main`.
2. **Merge method:** allow squash merging only (or squash and rebase), not
   merge commits, so that `main` stays linear. The scope check also refuses a
   pull request whose history has more than one merge base with `main` and
   compares `main` with the actual merge result, but a linear `main` keeps
   criss-cross histories from forming at all.
3. **Code owners:** add `.github/CODEOWNERS` naming the maintainers for
   `/.github/`, `/tools/`, `/env/`, `/scorer/`, `/runs/` and `/leaderboard/`,
   and turn on "require review from code owners" in the ruleset. (The file is
   not in the repository yet; it needs the maintainers' GitHub handles.)
4. **Actions:** keep the default workflow token read-only (the workflow also
   sets `permissions: contents: read`). A `pull_request_target` workflow runs on
   pull requests from forks without the approval step that `pull_request`
   workflows have, so anyone can start the check. It runs no code from the pull
   request, and one pull request can start at most ten validator jobs of up to
   90 minutes each (`MAX_SUBMISSIONS` in `tools/check_pr_scope.py`). If the
   check is abused, disable the workflow, or put the `submission` job behind a
   deployment environment with required reviewers.

## Reviewing a submission pull request

Every submission is reviewed by hand before it is merged, whatever its score.

1. `verdict` is green, and the pull request changes only one or more new
   folders `runs/submitted/<name>/` and `leaderboard/board.json`.
2. Open the `validate / submission (...)` log. The validator's `PASS` line
   ends with `REVIEW BY HAND: ...` when most of the run's calls (80% or more of
   the shorter record, at least 20 calls), in order, are the calls of a
   published scripted record or of another submission. ToolsEnabled cannot tell
   an edited scripted run from a model run; such a near copy is not merged
   unless the submitter shows that a model made it (for example with the
   client's session log, shared privately) and the explanation holds up. The
   model runs ToolsEnabled made share at most 54% of their calls with any
   scripted record. Repeated runs of one model can share more with each other:
   any two of the five `claude-opus-5-5` runs share 74% to 86% of the shorter
   run's calls, in order, so a second submission of the same model can be marked
   as a near copy of the first. That mark asks for a look at the session logs;
   on its own it is not a reason to refuse.
3. Read `RESULT.md`: its row `calls in common with a scripted record` gives the
   same count against the closest published scripted record, for every
   submission.
4. Read `SUBMISSION.json`: the prompt, the client, the agent's tool access
   (the repository holds complete correct solutions, so an agent that can read
   files could copy one) and the date.
5. Merge with squash. The push to `main` runs every test suite and
   `tools/build_board.py --check`; the site's board is a copy of
   `leaderboard/board.json`.

A pull request that changes anything else (code, documentation, a published
record, an existing submission) is a code change: `verdict` passes it as
`kind=code` when it touches nothing under `runs/` or `leaderboard/`, and fails
it when it mixes such changes with a submission. Review it as code.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
