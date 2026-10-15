# Head Gasket Bench 0.1.4 — native Windows and Codex packaging

These are the changes and operating boundaries. The published GitHub release
notes bind the exact source/archive hashes and measured acceptance scope.

The Windows launcher now creates run folders with a protected current-user DACL,
checks real NTFS directory handles and ownership, refuses reparse ancestors and
unsafe path forms, and retains non-delete-shared ancestor/folder handles plus a
private first-instance kernel pipe lease for the session lifetime. The lease is
keyed by the actual retained NTFS volume/file identity and current SID; it performs
no pipe communication and rejects remote clients. Directory write sharing allows
the pinned environment's atomic record replacement. A second server cannot clear
or reuse an active run.
SYSTEM and Administrators are trusted. This does not isolate hostile code running
as the same user. Windows run folders currently require local NTFS and ordinary
drive paths no longer than 240 characters; UNC, device namespaces and alternate
streams are refused. Existing folder permissions are inspected without repair.

The native ZIP includes the PSF CPython 3.12.3 embeddable runtime and its licence,
plus a PowerShell/cmd installer that verifies each payload file, refuses an
existing destination, creates a per-user private destination and prints MCP
configuration without editing any client settings. It requires no WSL, Unix
runtime, service, compiler, pip installation or global PATH change.

The Windows CLI explicitly uses UTF-8 for protocol output and diagnostics,
including Unicode request identifiers and paths, without CRLF translation.

The launcher reports 0.1.4. The scientific runtime, source epochs, configurations,
scorer, records, board and paper retain their published bytes. The pinned MCP
serverInfo version remains 0.1.0. Exact record replay still requires the Python
patch version that made the record.

The merged source's canonical Linux CLI suite passes 27/27; the Codex launcher
checks pass 3/3. Native qualification uses the bundled interpreter, fresh folders,
actual NTFS owner/raw-DACL/ancestor and writer-lock checks, Unicode stdio/record
verification, elevated engineering and a calibrated restricted medium token,
then a different worker's documented fresh-user pass. Consult the published
release receipt for those measured results rather than treating Linux skips or
predecessor native runs as evidence for a new archive. Windows 11 is untested.
Real Windows Codex host and console GUI acceptance remain owner-only.

The self-distributed Codex plugin keeps records outside the installation/cache,
forwards only the selected run folder/variant, and starts the canonical CLI
without installing packages or selecting a provider. The Windows ZIP's manifest
uses the bundled 3.12.3 interpreter through PLUGIN_ROOT; the Git/Linux manifest
retains python3. Windows server-entry tests do not prove a real Codex client
accepted that manifest. No OpenAI directory listing or approval is claimed.
