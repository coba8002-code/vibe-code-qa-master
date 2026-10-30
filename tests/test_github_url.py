import io
import zipfile
import pytest
from app.github_url import parse_repository


@pytest.mark.parametrize('value', [
    ' https://github.com/demo/sample ', 'github.com/demo/sample', 'demo/sample',
    'https://www.github.com/demo/sample/', 'https://github.com/demo/sample.git',
    'git@github.com:demo/sample.git', 'http://github.com/demo/sample',
    'https://github.com/demo/sample/tree/main/src',
    'https://github.com/demo/sample/blob/main/app.py?plain=1#L2',
    'https://github.com/demo/sample/pull/4',
    'https://github.com/demo/sample?tab=readme-ov-file',
])
def test_common_repository_links(value):
    assert parse_repository(value) == ('demo', 'sample')


@pytest.mark.parametrize('value', [
    '', 'https://github.com/demo', 'github.com/demo', 'https://evil.example/demo/sample',
    'https://github.com.evil.example/demo/sample', 'https://github.com@evil.example/demo/sample',
    'https://token@github.com/demo/sample', 'https://github.com:8080/demo/sample',
    'https://github.com/demo/..', 'https://github.com/demo/sample/tree/../escape',
    'https://github.com/demo%2fsample/repo', 'https://github.com/demo/sample\\evil',
    'https://github.com/demo/sample\n/evil', 'file:///demo/sample',
])
def test_invalid_or_credential_bearing_links(value):
    with pytest.raises(ValueError):
        parse_repository(value)


def test_quick_scan_normalizes_link_before_fetch(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('QA_ADMIN_TOKEN', 'test-only-url-token')
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive:
        archive.writestr('prefix/app.py', 'print(1)')
    requests = []
    def fetch(request, timeout):
        requests.append(request.full_url)
        if request.full_url.endswith('/demo/sample'):
            return io.BytesIO(b'{"default_branch":"main"}')
        if request.full_url.endswith('/commits/main'):
            return io.BytesIO(('{"sha":"' + 'a' * 40 + '"}').encode())
        return io.BytesIO(payload.getvalue())
    monkeypatch.setattr(main.urllib.request, 'urlopen', fetch)
    client = TestClient(main.app)
    response = client.post('/api/quick-scan/github', headers={'Authorization': 'Bearer test-only-url-token'},
                           json={'url': 'github.com/demo/sample/blob/main/app.py'})
    assert response.status_code == 200
    assert requests[-1] == 'https://api.github.com/repos/demo/sample/zipball/' + 'a' * 40
    assert response.json()['repository_url'] == 'https://github.com/demo/sample'
    assert response.json()['files_scanned'] == 1
