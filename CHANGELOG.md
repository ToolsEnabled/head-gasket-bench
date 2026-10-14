# Changelog

## 0.1.1 (2026-10-14)

- Validator: a run that stopped before reassembly can be submitted. The
  independent scorer reports some checklist items as unknown (for example on a
  part the run never touched); an unknown is no longer counted as a
  disagreement. Every determined shared field and every primary checkpoint must
  still agree. Found with a real early-stopping run; three unit tests.
- Pull-request check: submissions are validated with the base branch's
  validator, environment and scorer, never with code from the pull request; a
  submission pull request may change only `runs/submitted/<name>/` and
  `leaderboard/board.json`.
- Documentation: `look` returns about 196,000 characters, and Claude Code cuts
  MCP results above `MAX_MCP_OUTPUT_TOKENS` (25,000 tokens by default); both
  READMEs say to raise the limit and to check any client's limit.
- Board: a low-cost baseline, three runs of `claude-haiku-5-5` through Claude
  Code (0/18 each; scored results only).
- `env/`, `scorer/`, the configurations, the published records and the paper
  are unchanged.

## 0.1.0 (2026-10-14)

First public release.

- `env/`: the environment, an MCP stdio server with 18 tools and five
  variants; runtime `f347b0c8...` (hardened epoch `aecadda`) for new runs and
  the replay-only amended runtime `10967be0...` (epoch `24a5713`); V1-V5
  configurations byte-identical to the configurations in the published records.
- `scorer/`: the independent checkpoint scorer (scoring modules byte-identical
  to their sealed pins).
- `runs/`: the 13-case scripted family, the scripted V1 reference, and the
  scored results of three exploratory model runs (per-action agent traces not
  published).
- `paper/`: the report, v25 (64 pages), CC BY 4.0.
- `tools/validate_submission.py`, `tools/build_board.py`,
  `leaderboard/board.json`, the pull-request check, and the submission process.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
