import io
import subprocess
import urllib.error
import zipfile
import pytest
from app import github_auth, github_read


def test_existing_credential_is_noninteractive_and_not_persisted(monkeypatch):
    monkeypatch.delenv('QA_GITHUB_TOKEN')
    monkeypatch.setattr(github_auth.shutil, 'which', lambda _: 'git')
    def run(args, **kwargs):
        assert args == ['git', 'credential', 'fill']
        assert kwargs['env']['GIT_TERMINAL_PROMPT'] == '0'
        assert kwargs['env']['GCM_INTERACTIVE'] == 'never'
        assert kwargs['input'] == 'protocol=https\nhost=github.com\n\n'
        return subprocess.CompletedProcess(args, 0, 'username=demo\npassword=fixture-only\n')
    monkeypatch.setattr(github_auth.subprocess, 'run', run)
    assert github_auth.github_token() == 'fixture-only'


def test_missing_credential_does_not_prompt(monkeypatch):
    monkeypatch.delenv('QA_GITHUB_TOKEN')
    monkeypatch.setattr(github_auth.shutil, 'which', lambda _: None)
    assert github_auth.github_token() == ''


def test_authorization_is_not_forwarded_on_redirect():
    request = github_read._request('https://api.github.com/repos/demo/sample')
    redirected = urllib.request.HTTPRedirectHandler().redirect_request(
        request, None, 302, 'Found', {}, 'https://codeload.github.com/demo/sample/zip/main')
    assert request.get_header('Authorization')
    assert redirected.get_header('Authorization') is None


def fixture_fetch(monkeypatch, payload):
    def fetch(request, timeout):
        if request.full_url.endswith('/sample'):
            return io.BytesIO(b'{"default_branch":"main"}')
        if request.full_url.endswith('/commits/main'):
            return io.BytesIO(('{"sha":"' + 'b' * 40 + '"}').encode())
        return io.BytesIO(payload)
    monkeypatch.setattr(github_read.urllib.request, 'urlopen', fetch)


def test_large_archive_keeps_source_scan_budget(monkeypatch):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as z:
        z.writestr('root/video.bin', b'x' * 10000)
        z.writestr('root/app.py', b'print(1)')
        z.writestr('root/node_modules/dependency.js', b'eval(x)')
    monkeypatch.setattr(github_read, 'MAX_TOTAL_BYTES', 100)
    fixture_fetch(monkeypatch, payload.getvalue())
    report = github_read.fetch_snapshot('demo', 'sample')['report']
    assert report['files_scanned'] == 1
    assert report['files_skipped'] == 2


def test_download_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(github_read, 'MAX_ARCHIVE_BYTES', 10)
    fixture_fetch(monkeypatch, b'x' * 11)
    with pytest.raises(github_read.SnapshotError, match='256MB'):
        github_read.fetch_snapshot('demo', 'sample')


def test_private_repo_failure_is_actionable(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, None)
    monkeypatch.setattr(github_read.urllib.request, 'urlopen', fail)
    with pytest.raises(github_read.SnapshotError, match='비공개 저장소'):
        github_read.fetch_snapshot('demo', 'sample')
