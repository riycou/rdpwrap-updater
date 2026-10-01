# RDP Wrapper Updater

A portable Windows x64 updater that finds exact-build RDP Wrapper profiles in GitHub issue discussions, validates their structure, and backs up your existing `rdpwrap.ini` before applying a change.

**AI-generated project:** the application, tests, and documentation were generated with OpenAI Codex at the owner's direction. The running updater uses deterministic code, not an AI model. Posted offsets are read from community sources; the updater does not invent them. This is an experimental community tool, unaffiliated with Microsoft or the RDP Wrapper maintainers.

## Download and use

Download the ZIP from [Releases](https://github.com/riycou/rdpwrap-updater/releases), extract it, and open `RDPWrapUpdater.exe`. It starts a read-only check automatically when it finds your INI. Selecting a file with **Browse** also starts a check. Review the proposed changes and apply them if a validated profile is available. **Check for update** runs another check.

The default path is `C:\Program Files\RDP Wrapper\rdpwrap.ini`. A portable release needs no Python installation or AI model. Both packaged executables require administrator access at launch. Windows requests UAC consent before starting them unless the launching process is already elevated. The updater does not relaunch itself after a denied write. Python source runs must be started in an administrator terminal when updating protected files.

If the INI is missing, undecodable as UTF-8, or has missing/invalid global configuration sections, the updater builds a proposal from the bundled [base INI](assets/base.ini). The base contains global configuration, verified patch definitions, and 738 existing build profiles from the owner-provided baseline. Only a validated profile for your installed DLL is added. Existing files are backed up before replacement; read-only checks never create or replace the INI. UTF-16 files still require manual handling. A readable, usable INI is preserved, with only missing source-verified patch definitions added as needed. The output reports when the base is used and why. This creates configuration, not an RDP Wrapper installation.

```powershell
# Read-only check
.\RDPWrapUpdater.exe --ini "C:\Program Files\RDP Wrapper\rdpwrap.ini" --check

# Check and apply automatically, with no console window or prompts
.\RDPWrapUpdaterSilent.exe --ini "C:\Program Files\RDP Wrapper\rdpwrap.ini" --auto --silent

# Poll 50 recently updated issues, caching unchanged threads
.\RDPWrapUpdaterSilent.exe --ini "C:\Program Files\RDP Wrapper\rdpwrap.ini" --auto --silent --recent 50
```

Run automatic updates from an administrator terminal or an appropriately privileged task. Every changed INI gets a timestamped backup beside it. **Service restart is manual:** finish your RDP sessions before restarting Remote Desktop Services or rebooting. The GUI offers to stop services and retry if INI replacement is denied. It restores previously running services after the retry, including on failure. This disconnects RDP sessions; use it from the local screen. Silent/CLI runs can opt in with `--restart-service`; without this flag they never stop services.

## What it checks

- Reads `termsrv.dll`'s fixed binary version, which can differ from its displayed version string.
- Searches issue bodies and comments in [`stascorp/rdpwrap`](https://github.com/stascorp/rdpwrap).
- Requires a complete x64 patch/SLInit profile for the exact installed DLL version.
- Rejects unknown or misplaced fields, malformed offsets, conflicting posted values, and unsupported functions. Missing patch definitions can be copied exactly from fetched `[PatchCodes]` sections or the bundled source-verified base; existing conflicting definitions are not silently overwritten.
- Checks that main offsets fall within executable DLL sections and SLInit pointers within writable sections.
- Verifies the INI and DLL hashes before replacing the INI, writes atomically, and checks the resulting file.

These checks validate structure and some binary properties. They **do not prove that posted offsets patch the correct instructions or that RDP will work**. Real-world retrieval accuracy and runtime reliability of 99% have not been established.

## Shutdown polling and rolling issue log

Follow [SETUP-SHUTDOWN.txt](SETUP-SHUTDOWN.txt) to register [Shutdown-Update.ps1](Shutdown-Update.ps1) as a Windows Group Policy shutdown script. Registration is manual and requires administrator privileges on Windows Pro or a compatible edition. Extract the executable and script into an administrator-owned folder such as `C:\Program Files\RDPWrapUpdater`.

The poll selects the **50 most recently updated issues**, including closed issues. It compares issue timestamps, bodies, comment counts, labels, and state against the previous cache, and fetches comments only for changed threads. It retains the current 50 threads plus the last 250 issue-change records with issue numbers, URLs, labels, timestamps, and lock status. Labels are recorded locally; nothing is posted to GitHub.

An unchanged live test used one conditional GitHub request. A changed poll may need up to 55 requests, with a 40-second network budget and an 8-second maximum per request. Completed thread fetches are checkpointed; an incomplete poll cannot apply an INI. Rate limits, missing profiles, and network errors are logged, and the shutdown script lets shutdown continue. Local validation and disk operations add to overall run time.

Default CLI state is under `%LOCALAPPDATA%\RDPWrapUpdater`. The shutdown script uses `C:\ProgramData\RDPWrapUpdater`:

| File | Contents |
| --- | --- |
| `recent-issues.json` | Current thread cache, rolling issue history, and last poll statistics |
| `shutdown-runs.jsonl` | Shutdown check/update outcomes, source URLs, hashes, errors, and backup paths |

Use `--cache PATH` and `--log PATH` to override locations. `GITHUB_TOKEN` is optional and is not logged. A shutdown script running as SYSTEM does not inherit your interactive user's environment, so an optional token must be configured for that execution context. Do not commit tokens or logs.

## Command-line behavior

| Option | Behavior |
| --- | --- |
| `--ini PATH` or positional path | Existing INI to inspect/update |
| `--check` / `--dry-run` | Check without writing the INI |
| `--apply` / `--auto` | Check and apply a validated profile |
| `--silent` | Suppress application output; Windows can still request UAC consent at launch. Implies automatic apply unless `--check` is supplied |
| `--recent 50` | Poll/cache only the 50 most recently updated issues |
| `--cache PATH` | Recent-issue cache path |
| `--restart-service` | Stop RDP services during apply, then restore previously running services; disconnects RDP sessions |
| `--log PATH` | Append JSON run records to this path |
| `--offline --offline-file PATH` | Read profiles from your own reference INI |

Exit code `0` means the check/update completed successfully; `2` means an error or refusal. `--check` cannot be combined with `--apply` or `--auto`. Running either executable without a check/apply/silent flag opens the GUI.

## Build and test

The application uses Python's standard library, including Tkinter and Windows version APIs. Development was performed on Windows x64 with Python 3.14.4 and PyInstaller 6.22.3.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build.ps1
```

The public tests generate **fictional offsets** solely to test parsing; they are not Windows profiles. They cover accepted formatting, rejected mutations, source conflicts, DLL section bounds, backups, changed-file refusal, atomic-write failures, silent logs, cached polling, and rate-limit handling. Prior local tests also exercised collected real profiles and both packaged executables. Those parser results are not measurements of real-world RDP reliability.

## Limitations

- Live lookup reads issue bodies and comments; it does not download newly posted attachments or search other repositories.
- Recent-only mode can miss a matching profile outside the selected 50 issues. Default mode also uses the latest 50 issues. --recent 25 is available for a smaller poll.
- GitHub indexing, network availability, and rate limits can prevent discovery.
- The parser deliberately refuses incomplete or conflicting data; new schema conventions may need a code update.
- Only Windows x64 is supported. UTF-16 INI files require manual handling.
- Forced shutdowns and power loss cannot reliably run the hook. Windows may install a new DLL after the shutdown check.
- Executables are unsigned. No RDP runtime or actual shutdown test is claimed for this release.

## Contributing and license

Bug reports and pull requests are welcome. Include your DLL's fixed version, the source issue URL, the relevant error, and a minimal redacted example. Never upload credentials or private machine logs. Changes that accept new profiles should include both valid examples and malformed/conflicting examples.

The updater's original code, tests, and documentation are open source under the [MIT License](LICENSE). The upstream-derived base INI retains Apache-2.0 licensing and attribution. Third-party RDP Wrapper profiles retain their own authorship and terms; this distribution now bundles an owner-provided INI snapshot with its original attribution; it never includes Microsoft's DLLs. See [THIRD_PARTY.md](THIRD_PARTY.md).
