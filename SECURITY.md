# Security policy

Please report a security problem privately, not in a public issue:

- use **Report a vulnerability** on this repository's **Security** tab
  (GitHub's private vulnerability reporting), or
- email **security@toolsenabled.ai**.

Tell us the commit or release, what you found and how to reproduce it. We
reply as soon as we can, keep you informed while we fix it, and credit you in
the release notes if you want that. The latest release is the supported one;
fixes ship as a new release. Good-faith research under this policy is welcome
and authorized for ToolsEnabled's own code; please give us a reasonable chance
(up to 90 days) to fix a problem before you publish it. ToolsEnabled does not
pay rewards for reports. The full policy is at https://toolsenabled.ai/security/.

What the software does: the environment (`env/`) and the scorer (`scorer/`)
are Python 3.12 standard-library programs that open no sockets and read no
secrets; the environment verifies the hash of every runtime module before
running it (see `env/SECURITY.md`). The submission check
(`.github/workflows/validate.yml`) runs on `pull_request_target`, so GitHub
takes the workflow file from the main branch and a pull request cannot change
what its own check runs. Every script it runs comes from the main branch; the
pull request's commits are read with git and its files are checked out under
`pr/` as data, and nothing from the pull request is executed, imported or
installed. The token is read-only, no secrets are used, and no checkout keeps
credentials. `SUBMISSIONS.md` describes the check.

The environment is not a sandbox for the AI client that drives it: isolating
the agent is the job of the client and the person running it.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
