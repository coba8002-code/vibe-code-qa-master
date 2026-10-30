# VIBE CODE QA MASTER — Agent handoff and guarded modification

## Scope of this release

- Read GitHub default-branch commit metadata, then scan a SHA-pinned archive.
- Store read-only findings with `project_id`, `branch`, `revision`, time and evidence.
- Generate a revision-bound Markdown remediation brief for Codex or Claude Code.
- Never invoke Codex, Claude Code, GitHub write APIs, CI dispatch or Gabia deploy in this release.

## Manual execution after downloading a repair brief

1. Verify that the repository owner/name and 40-character SHA match the approved project.
2. Open an **isolated, disposable local checkout** in Codex or Claude Code at that SHA.
3. Paste the generated Markdown brief and ask for **analysis + proposed patch** only.
4. Run actual tests in a separate trusted TEST environment; do not expose PROD secrets.
5. Review the diff and tests. Require explicit authorization before any commit/push/PR.
6. On separate approval, create a new branch and PR (never push directly to `main`).
7. Require fresh CI evidence and human approval before merging or TEST deployment.

## Further implementation required for automated fixes

| Component | Implementation requirement | Gate |
|---|---|---|
| GitHub App | Repository allowlist + read-only installation by default | User approval |
| Agent runner | Ephemeral workspace, isolated credentials, command/output allowlist, budgets, cancel button | Explicit per-job approval |
| PR exporter | Short-lived GitHub App write token, branch allowlist, commit SHA validation | Separate write authorization |
| GitHub rulesets | Required CI, reviewed PRs, no bypass to `main` | Repository administrator |
| Gabia TEST | Versioned artifact, environment secrets, backup and rollback | Deployment approval |
| Gabia PROD | Separate credentials and manual release sign-off | Production owner |

## Important caveats

GitHub ZIP archives may contain untrusted instructions or malicious content. Never treat repository text as an instruction to the QA orchestration agent. A local Docker test environment is not a guarantee that hostile code cannot exploit the container runtime. Use dedicated test infrastructure and restrict credentials. A read-only static pattern scan is not a full security audit.
