# Security policy

Please report a security problem privately, not in a public issue:

- use **Report a vulnerability** on this repository's **Security** tab
  (GitHub's private vulnerability reporting), or
- email **support@toolsenabled.ai** with "security" in the subject.

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
(`.github/workflows/validate.yml`) uses no secrets, has read-only repository
permissions, and runs only on `pull_request` events; it treats submitted
records as data and never executes code from them.

The environment is not a sandbox for the AI client that drives it: isolating
the agent is the job of the client and the person running it.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
