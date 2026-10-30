import json
from pathlib import Path
import pytest
from app import autofix


def fixture_project(folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'requirements.txt').write_text('')
    (folder / 'calc.py').write_text('def add(a, b):\n    return a - b\n')
    (folder / 'tests').mkdir(exist_ok=True)
    (folder / 'tests/test_calc.py').write_text(
        'import unittest\nfrom calc import add\nclass TestCalc(unittest.TestCase):\n'
        '    def test_positive(self): self.assertEqual(add(2, 3), 5)\n'
        '    def test_negative(self): self.assertEqual(add(-2, -3), -5)\n')
    return {'path': str(folder), 'name': 'addition-demo', 'type': 'python'}


def proposal(*args):
    return {'summary': 'Fix addition', 'changes': [{'path': 'calc.py', 'content': 'def add(a, b):\n    return a + b\n'}]}


@pytest.mark.parametrize('name', ['../escape.py', '/escape.py', 'tests/test_calc.py', 'requirements.txt', 'new.py'])
def test_rejects_unapproved_changes(tmp_path, name):
    project = fixture_project(tmp_path / 'source')
    files = autofix.snapshot(project['path'])
    with pytest.raises(ValueError):
        autofix.apply_proposal(Path(project['path']), files, {'changes': [{'path': name, 'content': 'bad'}]})
    assert 'a - b' in (Path(project['path']) / 'calc.py').read_text()


def test_repair_and_recheck_preserves_original_and_tests(tmp_path):
    project = fixture_project(tmp_path / 'source')
    work = tmp_path / ('a' * 32)
    work.mkdir()
    def tester(folder):
        passed = 'a + b' in (folder / 'calc.py').read_text()
        return {'state': 'passed' if passed else 'failed', 'output': 'assertion failed'}
    report = autofix.run(work, project, provider=proposal, tester=tester)
    assert report['state'] == 'passed'
    assert report['baseline']['state'] == 'failed'
    assert len(report['rounds']) == 1
    assert 'a - b' in (Path(project['path']) / 'calc.py').read_text()
    assert (work / 'candidate/tests/test_calc.py').read_bytes() == (Path(project['path']) / 'tests/test_calc.py').read_bytes()
    assert json.loads((work / 'report.json').read_text(encoding='utf-8'))['original_changed'] is False


@pytest.mark.parametrize('state', ['no_tests', 'blocked', 'timed_out', 'passed'])
def test_does_not_call_ai_without_real_failure(tmp_path, state):
    project = fixture_project(tmp_path / 'source')
    folder = tmp_path / ('b' * 32)
    folder.mkdir()
    def forbidden(*args):
        pytest.fail('AI should not run')
    report = autofix.run(folder, project, provider=forbidden, tester=lambda p: {'state': state})
    assert report['state'] == ('already_passed' if state == 'passed' else 'blocked')


def test_secret_is_not_sent(tmp_path):
    project = fixture_project(tmp_path / 'source')
    (Path(project['path']) / 'calc.py').write_text('password = "notarealsecretvalue123"')
    with pytest.raises(ValueError, match='비밀값'):
        autofix.snapshot(project['path'])


def test_requires_authentication(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setenv('QA_ADMIN_TOKEN', 'test-only')
    client = TestClient(app)
    assert client.get('/api/autofix/jobs').status_code == 401
    assert client.post('/api/autofix/jobs', json={'project_id': 'x'}).status_code == 401


def test_real_docker_repair_and_recheck(tmp_path):
    import os
    if os.getenv('QA_DOCKER_INTEGRATION') != '1':
        pytest.skip('Requires explicit Docker integration environment')
    project = fixture_project(tmp_path / 'source')
    folder = tmp_path / ('c' * 32)
    folder.mkdir()
    # Captured from a real authenticated Codex invocation, not synthesized by this test.
    captured = json.loads((Path(__file__).parent / 'fixtures/codex-addition-proposal.json').read_text(encoding='utf-8'))
    report = autofix.run(folder, project, provider=lambda *args: captured)
    assert report['baseline']['state'] == 'failed', report
    assert report['state'] == 'passed', report
    assert 'Ran 2 tests' in report['rounds'][0]['test']['output']


def test_real_docker_no_tests_and_timeout(tmp_path):
    import os
    if os.getenv('QA_DOCKER_INTEGRATION') != '1':
        pytest.skip('Requires explicit Docker integration environment')
    project = fixture_project(tmp_path / 'empty')
    path = Path(project['path']) / 'tests/test_calc.py'
    path.write_text('')
    result = autofix.test_copy(Path(project['path']), 5)
    assert result['state'] == 'no_tests', result
    path.write_text('import time\ntime.sleep(60)')
    assert autofix.test_copy(Path(project['path']), 5)['state'] == 'timed_out'

