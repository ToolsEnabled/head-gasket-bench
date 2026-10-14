# Contributing

Issues and pull requests are welcome: bug reports, corrections to the
documentation or the report, and fixes to the environment, the scorer or the
tools. Please open an issue first for anything larger than a small fix.

- Runs are submitted by pull request; see [SUBMISSIONS.md](SUBMISSIONS.md).
- The environment's runtime modules and the scorer's scoring modules are
  pinned by hash, and every published record depends on those exact bytes.
  A change to them is a new epoch, not a fix: it needs new pins and new runs,
  and the published records stay as they are.
- Before you open a pull request, run the tests:
  `(cd env && python3 -m unittest discover -s tests)`,
  `(cd scorer && python3 -m unittest discover -s tests)` and
  `python3 -m unittest discover -s tests`.
- Standard library only; no network access in any code path.
- Contributions are accepted under the repository's licences (MIT for code
  and data, CC BY 4.0 for `paper/`).

Questions: open an issue or write to support@toolsenabled.ai.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
