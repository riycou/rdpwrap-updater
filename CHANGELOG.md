# Changelog

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
