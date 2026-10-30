from fastapi.testclient import TestClient
from app import main


def test_browser_login_is_single_use_and_no_store(monkeypatch):
    monkeypatch.setenv('QA_ADMIN_TOKEN', 'fixture-admin')
    client = TestClient(main.app)
    code = main.browser_login_code()
    assert client.post('/api/session/browser', json={'code': 'invalid-code-of-sufficient-length'}).status_code == 401
    response = client.post('/api/session/browser', json={'code': code})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/projects').status_code == 401
    assert client.post('/api/session/browser', json={'code': code}).status_code == 401


def test_browser_login_expires_and_new_code_invalidates_old(monkeypatch):
    monkeypatch.setenv('QA_ADMIN_TOKEN', 'fixture-admin')
    client = TestClient(main.app)
    first = main.browser_login_code()
    second = main.browser_login_code()
    assert client.post('/api/session/browser', json={'code': first}).status_code == 401
    monkeypatch.setattr(main.time, 'monotonic', lambda: float('inf'))
    assert client.post('/api/session/browser', json={'code': second}).status_code == 401
