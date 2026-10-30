---
name: vibe-code-qa-master
description: Audit and validate vibe-coded repositories with evidence-backed security, functionality, performance, resource, soak/stress and deployment QA. Use for Codex or Claude Code projects when preparing a PR, release, staging deployment, production gate or incident investigation.
---

# VIBE CODE QA MASTER

1. Read repository instructions, current branch, stack and test configuration first; preserve unrelated edits.
2. Identify the explicitly authorized repository and environment. Do not install dependencies, push, deploy, or send heavy traffic to external systems without applicable authority.
3. Pin the examined commit SHA. Create an inventory of runnable tests. Mark missing tests `not_run`, never `pass`.
4. Use official tools where installed: Codex Security / CodeQL or Semgrep for code, dependency auditors, pytest / unit tests, Playwright for browser flows, k6 for load/soak, OS profiler or Prometheus for resource baselines. Do not imply these tools are present without checking.
5. Run safe, deterministic checks locally or in isolated CI. For destructive, fuzz, DAST, load, soak, chaos or migration exercises require an explicitly designated disposable TEST target. Never run against production by default.
6. Investigate root causes and verify repairs with the original failing case and a regression test. Prefer a proposed PR over silent mutation. Don't auto-merge.
7. Generate an evidence report by category `security,functional,performance,resources,hardtest` with commit SHA, runtime, tool versions, results, missing coverage, limitations and artifacts.
8. Block release if a mandatory category is `fail`, `warning` or `not_run` unless a documented approval policy explicitly handles exceptions; report residual risks without claiming perfect security.
9. Separate Gabia TEST and PROD DB, storage, secrets, runtime accounts and backup; production release requires approval, health check and rollback plan.

## Connections

- Read [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) for platform API, event schema, release gates and phased integration.
- For existing PC activity, collect only authorized, allowlisted lifecycle metadata through agent hooks/OTel and scoped device credentials; exclude prompts, code and tool output.
- If the project source has not been imported, prepare the QA harness but report application verification as `not_run`.
