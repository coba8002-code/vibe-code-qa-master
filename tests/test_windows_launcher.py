import urllib.request


def test_desktop_server_starts_without_console(monkeypatch, tmp_path):
    import sys
    from app import main
    import windows_launcher as launcher

    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'qa.sqlite3')
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    opened, errors = [], []
    monkeypatch.setattr(launcher.webbrowser, 'open', opened.append)
    monkeypatch.setattr(launcher.messagebox, 'showerror', lambda *args: errors.append(args))
    instance = launcher.Launcher.__new__(launcher.Launcher)
    instance.server = None
    instance.url = None
    instance.status = type('Status', (), {'set': lambda self, value: None})()
    try:
        instance.open()
        assert not errors
        assert opened == [instance.url]
        with urllib.request.urlopen(instance.url + '/api/health', timeout=5) as response:
            assert response.status == 200
        instance.open()
        assert opened == [instance.url, instance.url]
    finally:
        if instance.server:
            instance.server.should_exit = True
