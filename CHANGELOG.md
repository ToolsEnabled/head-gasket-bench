# Changelog

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
