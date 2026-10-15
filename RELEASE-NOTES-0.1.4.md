# Head Gasket Bench 0.1.4 — Windows candidate

Prepared on `windows-port`; not published and not ready for release.

The Windows launcher now creates run folders with a protected current-user DACL,
checks real NTFS directory handles and ownership, refuses reparse ancestors and
unsafe path forms, and retains an exclusive writer handle plus ancestor handles
for the session lifetime. A second server cannot clear or reuse an active run.
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

Qualification so far: Linux launcher suite 26/26 on the pre-version-change
candidate; five native folder/ACL/lock/path tests and scientific pins on Windows
10 Pro 22H2 build19045 with CPython3.12.3. These native checks used elevated SSH.
Final candidate installation, stdio replay/verify, expanded security checks,
independent fresh-folder review and ordinary-user acceptance remain pending.
Windows11 has not been tested. Do not publish this candidate as qualified.
