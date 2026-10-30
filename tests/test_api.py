import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_packaging_spec_resolves_actual_project_root():
    spec = Path(__file__).resolve().parents[1] / "windows" / "VibeQAMaster.spec"
    source = spec.read_text(encoding="utf-8")
    assert 'root = Path(SPECPATH).resolve().parent' in source
    assert 'root / "windows_launcher.py"' in source
    assert 'root / "ui" / "index.html"' in source


def test_packaged_app_self_check_keeps_user_db_isolated(monkeypatch, tmp_path):
    import windows_launcher
    from app import main

    original_path = main.DB_PATH
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "existing.sqlite3")
    try:
        windows_launcher.self_check()
        assert not (tmp_path / "existing.sqlite3").exists()
    finally:
        main.DB_PATH = original_path


def test_project_approval_event_dedup_and_deployment_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "a-secret-admin-token")
    monkeypatch.setenv("QA_AGENT_TOKEN", "another-agent-token")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    a = {"Authorization": "Bearer a-secret-admin-token"}
    e = {"Authorization": "Bearer another-agent-token"}
    assert client.get("/api/projects").status_code == 401
    p = client.post("/api/projects", headers=a, json={"owner": "coba8002-code", "repo": "Webjux"}).json()
    assert p["state"] == "pending"
    payload = {"event_id": "event-12345678", "project_id": p["id"], "provider": "codex",
               "device": "pc1", "status": "started", "timestamp": "2026-10-23T00:00:00Z",
               "metadata": {"run_id": "1", "prompt": "private text"}}
    assert client.post("/api/events", headers=e, json=payload).status_code == 409
    assert client.post(f"/api/projects/{p['id']}/approve", headers=a).status_code == 200
    assert client.post("/api/events", headers=e, json=payload).json()["accepted"]
    assert not client.post("/api/events", headers=e, json=payload).json()["accepted"]
    assert "private text" not in client.get("/api/events", headers=a).json()[0]["metadata"]
    revision = "abcdef12345"
    assert client.get(f"/api/reports/{p['id']}?revision={revision}", headers=a).json()["verdict"] == "incomplete"
    req = {"project_id": p["id"], "environment": "production", "revision": revision}
    assert client.post("/api/deployments", headers=a, json=req).status_code == 409
    for category in main.CATEGORIES:
        assert client.post("/api/checks", headers=a, json={
            "project_id": p["id"], "revision": revision, "category": category,
            "outcome": "pass", "details": "test fixture"}).status_code == 200
    assert client.get(f"/api/reports/{p['id']}?revision={revision}", headers=a).json()["verdict"] == "pass"
    request = client.post("/api/deployments", headers=a, json=req).json()
    assert request["executed"] is False
    assert client.post(f"/api/deployments/{request['id']}/approve", headers=a).json()["executed"] is False


def test_empty_admin_secret_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.delenv("QA_ADMIN_TOKEN", raising=False)
    from app import main
    importlib.reload(main)
    assert TestClient(main.app).get("/api/projects").status_code == 401


def test_release_readiness_never_claims_windows_or_real_repo_verified(monkeypatch):
    monkeypatch.setenv("QA_ADMIN_TOKEN", "readiness-admin")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    assert client.get("/api/release-readiness").status_code == 401
    ready = client.get("/api/release-readiness", headers={"Authorization": "Bearer readiness-admin"}).json()
    assert ready["release_ready"] is False
    assert ready["windows_installer_tested"] == "not_verified"
    assert ready["real_repository_qa"] == "not_verified"


def test_quick_scan_rules_are_read_only_and_redacted():
    from app.scanner import scan
    result = scan([
        ("project/app.py", b'password = "verysecretpassword12345"\neval(payload)\n'),
        ("project/tests/test_app.py", b'def test_ok(): pass\n'),
        ("project/.github/workflows/qa.yml", b'name: QA\n'),
        ("project/requirements.txt", b'fastapi\n'),
        ("../untrusted.py", b'eval(payload)\n'),
    ], "fixture")
    assert result["files_scanned"] == 4
    assert result["files_skipped"] == 1
    assert result["checks"]["test_files"] == "present"
    assert result["checks"]["github_actions"] == "present"
    assert any(f["rule"] == "SEC001" for f in result["findings"])
    assert "verysecretpassword" not in str(result)
    assert "runtime" in result["not_run"]


def test_local_upload_and_github_url_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "test-admin")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    auth = {"Authorization": "Bearer test-admin"}
    assert client.post("/api/quick-scan/local", files=[("files", ("app.py", b"eval(x)", "text/plain"))],
                       data={"paths": "project/app.py"}).status_code == 401
    result = client.post("/api/quick-scan/local", headers=auth,
                         files=[("files", ("app.py", b"eval(x)", "text/plain"))],
                         data={"paths": "project/app.py"})
    assert result.status_code == 200
    assert result.json()["findings"][0]["rule"] == "SEC002"
    assert client.post("/api/quick-scan/github", headers=auth,
                       json={"url": "https://evil.example/repo"}).status_code == 400


def test_runtime_is_opt_in_and_docker_absence_is_blocked(tmp_path, monkeypatch):
    import time
    from app import runtime, main
    (tmp_path / "requirements.txt").write_text("# fixture\n")
    approved = runtime.register(str(tmp_path))
    monkeypatch.setattr(runtime, "_docker_available", lambda _: (False, "No Docker"))
    importlib.reload(main)
    monkeypatch.setenv("QA_ADMIN_TOKEN", "admin-test")
    client = TestClient(main.app)
    a = {"Authorization": "Bearer admin-test"}
    request = {"project_id": approved["id"], "mode": "functional", "duration_seconds": 5}
    assert client.post("/api/runtime/jobs", headers=a, json=request).status_code == 400
    request["confirmed"] = True
    assert client.post("/api/runtime/jobs", headers=a, json=request).status_code == 200
    for _ in range(40):
        row = client.get("/api/runtime/jobs", headers=a).json()[0]
        if row["state"] != "queued" and row["state"] != "running":
            break
        time.sleep(0.01)
    assert row["state"] == "blocked"
    assert row["cycles"] == 0


def test_local_load_target_is_restricted(tmp_path, monkeypatch):
    from app import main
    importlib.reload(main)
    monkeypatch.setenv("QA_ADMIN_TOKEN", "admin-test")
    client = TestClient(main.app)
    a = {"Authorization": "Bearer admin-test"}
    for url in ("https://127.0.0.1:3000", "http://example.com:3000/health",
                "http://127.0.0.1:80", "http://localhost:3000@evil.com/test"):
        assert client.post("/api/load/jobs", headers=a,
                           json={"url": url, "requests": 1, "concurrency": 1,
                                 "confirmed": True}).status_code == 400
    assert client.post("/api/load/jobs", headers=a,
                       json={"url": "http://127.0.0.1:3000/health", "requests": 1,
                             "concurrency": 1, "confirmed": False}).status_code == 400


def test_opt_in_local_probe_reports_latency():
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from app import loadtest

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"healthy")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = loadtest.start(f"http://127.0.0.1:{server.server_port}/health", 4, 2, True)
        for _ in range(100):
            row = next(j for j in loadtest.jobs() if j["id"] == result["id"])
            if row["state"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        assert row["state"] == "passed"
        assert row["completed"] == 4
        assert row["errors"] == 0
        assert row["p95_ms"] >= 0
    finally:
        server.shutdown()


def test_execution_report_does_not_claim_untested_categories(tmp_path, monkeypatch):
    from app import main
    importlib.reload(main)
    monkeypatch.setenv("QA_ADMIN_TOKEN", "test-admin")
    client = TestClient(main.app)
    assert client.get("/api/execution-report").status_code == 401
    result = client.get("/api/execution-report", headers={"Authorization": "Bearer test-admin"})
    assert result.status_code == 200
    assert result.json()["coverage"]["functional"] == "not_verified"
    assert "warning" in result.json()


def test_approved_github_snapshot_generates_draft_without_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "read-only-admin")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    auth = {"Authorization": "Bearer read-only-admin"}
    project = client.post("/api/projects", headers=auth,
                          json={"owner": "coba8002-code", "repo": "Webjux"}).json()

    def fake_read(owner, repo):
        assert (owner, repo) == ("coba8002-code", "Webjux")
        return {"branch": "main", "revision": "a" * 40, "visibility": "public",
                "report": {"findings": [{"rule": "SEC002", "severity": "medium",
                                          "title": "동적 실행", "path": "src/app.py", "line": 12}],
                           "files_scanned": 1, "files_skipped": 0, "risk": "review",
                           "checks": {}, "notice": "static only", "not_run": ["runtime"]}}

    monkeypatch.setattr(main, "fetch_snapshot", fake_read)
    assert client.post(f"/api/projects/{project['id']}/sync", headers=auth).status_code == 409
    client.post(f"/api/projects/{project['id']}/approve", headers=auth)
    scan = client.post(f"/api/projects/{project['id']}/sync", headers=auth)
    assert scan.status_code == 200
    assert scan.json()["revision"] == "a" * 40
    assert scan.json()["note"].startswith("Read-only")
    history = client.get("/api/scans", headers=auth).json()
    assert len(history) == 1
    draft = client.post("/api/repair-drafts", headers=auth,
                        json={"scan_id": history[0]["id"], "provider": "codex"})
    assert draft.status_code == 200
    assert draft.json()["status"] == "draft"
    assert draft.json()["github_write"] is False
    assert draft.json()["execution_started"] is False
    assert "src/app.py:12" in draft.json()["instructions"]
    assert "do not push" in draft.json()["instructions"].lower()
    assert client.get("/api/repair-drafts", headers=auth).json()[0]["status"] == "draft"


def test_github_snapshot_pin_uses_commit_hash_and_limits(tmp_path, monkeypatch):
    import io
    import json
    import zipfile
    from app import github_read

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("repo-root/src/app.py", "eval(input())")

    class Response:
        def __init__(self, content):
            self.content = content

        def __enter__(self):
            return io.BytesIO(self.content)

        def __exit__(self, *_):
            return False

    urls = []

    def fake_urlopen(request, timeout=15):
        urls.append(request.full_url)
        if request.full_url.endswith("/Webjux"):
            return Response(json.dumps({"default_branch": "main", "visibility": "public"}).encode())
        if request.full_url.endswith("/commits/main"):
            return Response(json.dumps({"sha": "b" * 40}).encode())
        return Response(archive_bytes.getvalue())

    monkeypatch.setattr(github_read.urllib.request, "urlopen", fake_urlopen)
    result = github_read.fetch_snapshot("coba8002-code", "Webjux")
    assert urls[-1].endswith("/zipball/" + "b" * 40)
    assert result["revision"] == "b" * 40
    assert result["report"]["findings"][0]["rule"] == "SEC002"


def test_patch_proposal_review_only_never_applies_or_pushes(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "patch-admin")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    auth = {"Authorization": "Bearer patch-admin"}
    project = client.post("/api/projects", headers=auth,
                          json={"owner": "demo", "repo": "sample"}).json()
    client.post(f"/api/projects/{project['id']}/approve", headers=auth)
    with main.connection() as con:
        scan_id = con.execute("INSERT INTO scan_runs(project_id,revision,branch,result,created_at) VALUES(?,?,?,?,?)",
                              (project["id"], "a" * 40, "main", '{"findings": []}', main.utcnow())).lastrowid
        draft_id = con.execute("INSERT INTO repair_drafts(scan_id,provider,status,instructions,created_at) VALUES(?,?,?,?,?)",
                               (scan_id, "codex", "draft", "Review only", main.utcnow())).lastrowid
    safe_diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
    bad = safe_diff.replace("a/app.py b/app.py", "a/../escape.py b/../escape.py")
    assert client.post("/api/patch-proposals", headers=auth,
                       json={"draft_id": draft_id, "patch": bad, "summary": "unsafe"}).status_code == 400
    response = client.post("/api/patch-proposals", headers=auth,
                           json={"draft_id": draft_id, "patch": safe_diff, "summary": "change line"})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["applied"] is False and proposal["github_write"] is False
    assert client.get(f"/api/patch-proposals/{proposal['id']}", headers=auth).json()["patch"] == safe_diff
    reviewed = client.post(f"/api/patch-proposals/{proposal['id']}/review", headers=auth,
                           json={"decision": "approved_for_export"})
    assert reviewed.status_code == 200 and reviewed.json()["applied"] is False
    assert client.post(f"/api/patch-proposals/{proposal['id']}/review", headers=auth,
                       json={"decision": "rejected"}).status_code == 409


def test_recheck_comparison_tracks_resolved_remaining_and_new(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "recheck-admin")
    from app import main
    from app.scanner import scan
    import json
    importlib.reload(main)
    client = TestClient(main.app)
    auth = {"Authorization": "Bearer recheck-admin"}
    project = client.post("/api/projects", headers=auth,
                          json={"owner": "demo", "repo": "sample"}).json()
    before = scan([("src/old.py", b"eval(x)\n"), ("src/keep.py", b"eval(x)\n")], "baseline")
    with main.connection() as con:
        scan_id = con.execute("INSERT INTO scan_runs(project_id,revision,branch,result,created_at) VALUES(?,?,?,?,?)",
                              (project["id"], "a" * 40, "main", json.dumps(before), main.utcnow())).lastrowid
    uploads = [
        ("files", ("old.py", b"print('safe')\n", "text/plain")),
        ("files", ("keep.py", b"eval(x)\n", "text/plain")),
        ("files", ("new.py", b"exec(x)\n", "text/plain")),
    ]
    paths = {"paths": ["project/src/old.py", "project/src/keep.py", "project/src/new.py"]}
    assert client.post(f"/api/scans/{scan_id}/recheck", headers=auth,
                       files=uploads, data=paths).status_code == 409
    client.post(f"/api/projects/{project['id']}/approve", headers=auth)
    assert client.post(f"/api/scans/{scan_id}/recheck", headers=auth,
                       files=uploads, data={"paths": ["project/../bad.py", *paths["paths"][1:]]}).status_code == 400
    response = client.post(f"/api/scans/{scan_id}/recheck", headers=auth,
                           files=uploads, data=paths)
    assert response.status_code == 200
    result = response.json()
    assert result["github_write"] is False and result["code_executed"] is False
    compared = result["comparison"]
    assert compared["resolved_candidates"] == [{"rule": "SEC002", "path": "src/old.py"}]
    assert compared["remaining"] == [{"rule": "SEC002", "path": "src/keep.py"}]
    assert compared["new_findings"] == [{"rule": "SEC002", "path": "src/new.py"}]
    assert compared["verdict"] == "review_required"
    assert len(client.get("/api/rechecks", headers=auth).json()) == 1
    followup = client.post(f"/api/rechecks/{result['id']}/followup", headers=auth,
                           json={"provider": "codex"})
    assert followup.status_code == 200
    draft = followup.json()
    assert draft["round"] == 1 and draft["execution_started"] is False
    assert draft["github_write"] is False
    assert "src/keep.py" in draft["instructions"]
    assert "src/new.py" in draft["instructions"]
    assert "do not push" in draft["instructions"].lower()
    duplicate = client.post(f"/api/rechecks/{result['id']}/followup", headers=auth,
                            json={"provider": "codex"}).json()
    assert duplicate["id"] == draft["id"]
    assert duplicate["round"] == 1
    assert len(client.get("/api/followup-drafts", headers=auth).json()) == 1
    assert client.get(f"/api/followup-drafts/{draft['id']}", headers=auth).status_code == 200


def test_followup_refuses_zero_remaining_findings(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "qa.sqlite3"))
    monkeypatch.setenv("QA_ADMIN_TOKEN", "safe-admin")
    from app import main
    importlib.reload(main)
    client = TestClient(main.app)
    auth = {"Authorization": "Bearer safe-admin"}
    p = client.post("/api/projects", headers=auth, json={"owner": "demo", "repo": "sample"}).json()
    client.post(f"/api/projects/{p['id']}/approve", headers=auth)
    with main.connection() as con:
        scan_id = con.execute("INSERT INTO scan_runs(project_id,revision,branch,result,created_at) VALUES(?,?,?,?,?)",
                              (p["id"], "b" * 40, "main", '{"findings": []}', main.utcnow())).lastrowid
        recheck_id = con.execute("INSERT INTO recheck_runs(scan_id,result,created_at) VALUES(?,?,?)",
                                 (scan_id, json.dumps({"remaining": [], "new_findings": [],
                                                       "files_skipped": 0}), main.utcnow())).lastrowid
    assert client.post(f"/api/rechecks/{recheck_id}/followup", headers=auth,
                       json={"provider": "claude-code"}).status_code == 409
