from app.external_tools import windows_tool, find_tool


def test_vendor_installations_without_path(tmp_path):
    docker = tmp_path / 'Programs/DockerDesktop/resources/bin/docker.exe'
    older = tmp_path / 'OpenAI/Codex/bin/older/codex.exe'
    current = tmp_path / 'OpenAI/Codex/bin/current/codex.exe'
    for path in (docker, older, current):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test fixture only')
    import os
    os.utime(older, (100, 100))
    os.utime(current, (200, 200))
    env = {'LOCALAPPDATA': str(tmp_path)}
    assert windows_tool('docker', env) == str(docker)
    assert windows_tool('codex', env) == str(current)
    assert windows_tool('unknown', env) is None
    assert windows_tool('codex', {}) is None


def test_path_tool_takes_precedence(monkeypatch):
    from app import external_tools
    monkeypatch.setattr(external_tools.shutil, 'which', lambda name: '/configured/codex')
    assert find_tool('codex') == '/configured/codex'
