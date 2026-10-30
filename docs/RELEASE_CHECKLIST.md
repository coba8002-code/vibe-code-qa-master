# VIBE CODE QA MASTER — Windows release gate

This is a release checklist, not a declaration of production readiness.

## Evidence-based gates

| Gate | Passing evidence | Current status (2026-10-24) |
|---|---|---|
| G1. Backend/API regression | `python -m pytest -q`, all tests pass | 16 tests passed in Linux sandbox; rerun on Windows for release |
| G2. Frontend syntax | `node --check ui/workflow.js` | Passed in Linux sandbox; rerun for release |
| G3. Read-only GitHub behavior | No authenticated GitHub write request in code; read-only snapshot tests | Basic automated tests passed; live private repo unverified |
| G4. Windows EXE startup | Bundled `--self-check` plus `windows/smoke-windows.ps1` pass on Windows | NOT RUN |
| G5. Installer success | Silent install, installed `--self-check`, and startup via `windows/verify-installer.ps1` | NOT RUN |
| G6. UI end-to-end | On Windows: open browser UI, set token, scan local fixture, inspect results, restart | NOT RUN |
| G7. Runtime Docker sandbox | Approved isolated fixture; Python/Node tests; resource and timeout evidence | NOT RUN on Windows |
| G8. Security and distribution | Signed release or explicit unsigned-app trust handling, dependency review, AV scan | NOT RUN |

Do not call the app Windows-ready until at least G1–G7 pass on the release candidate. Do not call it production-security-certified merely because those gates pass.

## User-facing workflow smoke test

1. Build on Windows 10/11 with Python 3.12 and Inno Setup 6, or run the manual GitHub Actions Windows build **in a separate user-authorized repository**.
2. Preserve `release/VibeCodeQAMaster-Setup.exe` and `release/SHA256SUMS.txt`. Match the SHA-256 against the installer.
3. Install and launch the executable, choose **검수 화면 열기**; confirm that `127.0.0.1` opens and `/api/health` works.
   The Windows smoke scripts also invoke `VibeQAMaster.exe --self-check`, validating bundled UI assets, API authorization and an isolated temporary SQLite store.
4. Copy administrator key from the launcher. Confirm unauthorized API requests receive HTTP 401.
5. Scan a small non-sensitive local fixture and verify scanned/skipped counts and warning wording.
6. Add an approved GitHub test repository, run SHA-pinned scan, generate Codex/Claude repair brief.
7. Create a textual `.diff` in the fixture, register and review it. Confirm no repo write, push, PR, or deployment occurred.
8. Select a modified fixture local folder and run static recheck; validate resolved/remaining/new groups and follow-up brief.
9. If Docker Desktop is deliberately enabled for testing, register only the fixture folder and run bounded functional/soak tests; observe blocked/missing-image states too.
10. With a user-owned localhost test endpoint, run bounded HTTP load test; never target production or unrelated hosts.

## External authority required

- This source tree is **not** a Windows installer. Building a Windows `.exe` requires a Windows execution environment.
- Uploading files, creating an external GitHub repository, triggering Actions, creating a PR, or requesting write tokens requires separate user authorization.
- Running Docker tests on someone else's project requires approval of the particular local folder and execution risk.
- Production deployment remains disconnected intentionally.

## Safety acceptance criteria

- GitHub access is read-only unless an additional, dedicated write workflow is separately authorized.
- Proposed patch approval grants manual export, never silent apply.
- A static finding disappearing is only a *resolved candidate*. No automatic PASS.
- Preserve NOT_RUN for unavailable functionality, resource/soak and security checks.
- Block release when installer smoke fails, API tests fail, or Windows behavior has not been observed.
