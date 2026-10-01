# Changelog

## 1.2.5 — 2026-10-01

- Offer a service-stop retry when an elevated GUI cannot replace the INI.
- Add explicit `--restart-service` for unattended apply. Restore previously running dependent services even if stopping or writing fails.
- User reported successful fresh INI creation and RDPConf fully supported/listening for 10.0.26100.9444 after stopping TermService. Actual RDP connections remain unverified.

## 1.2.4 — 2026-10-01

- Bundles the owner-provided installed INI as a baseline, retaining 738 existing profiles and attribution.
- Defaults to the 50 most recently updated issues with cached comments. Shutdown polling also uses 50 issues.
- Separates 25/50-issue conditional caches and allows up to 55 requests within the network budget for a 50-issue poll.

## 1.2.3 — 2026-10-01

- Handles the Windows read-only attribute during atomic INI replacement, restoring it after success or failure.
- Write errors now show the exact Windows error, INI path, version, and administrator-token status.
- Added a Windows read-only replacement/failure regression test. File locks and access-control errors are not bypassed.

## 1.2.2 — 2026-10-01

- Both packaged executables now require administrator access through their Windows manifest.
- Removed the application elevation retry prompt and relaunch loop. A denied write now reports an error without spawning another instance.
- Silent/background execution must start elevated (the shutdown hook already runs as SYSTEM).

## 1.2.1 — 2026-10-01

- Fixed the GUI layout that hid Check and Apply below the expanding text area.
- Kept action buttons visible at the default window size and minimum size.
- Automatically starts a read-only check when the existing INI is found or selected with Browse.
- Reads Tkinter variables on the UI thread and disables overlapping checks.
- Added GUI regression tests for layout, startup, and file selection. Applying remains an explicit action.
- Added a licensed upstream-based INI template for missing or unusable configurations, with backups before replacement and exclusive creation of new files.
- Added exact missing patch definitions from fetched sources or the source-verified base, including the `mov_eax_1_nop_2` failure reported by a user. Conflicting definitions still refuse the update.

## 1.2.0 — 2026-10-01

Initial public MIT-licensed release, generated with OpenAI Codex.

- GUI and portable Windows x64 executables.
- Exact fixed-version DLL detection and strict patch/SLInit schema validation.
- Silent automatic updates with backups, atomic writes, JSON logs, and exit codes.
- Polling of the 25 most recently updated issues, conditional requests, cached comments, and a rolling 250-change issue history.
- Bounded network work and checkpointed thread downloads.
- Windows shutdown script and administrator setup instructions.
- Self-contained synthetic tests and Windows build workflow.

Public builds do not bundle a community INI corpus. Optional offline mode reads a user-supplied reference file. Service restart remains manual; real-world 99% accuracy is not claimed.
