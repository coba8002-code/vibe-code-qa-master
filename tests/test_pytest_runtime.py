import os
import pytest
from app import runtime, autofix


def test_pytest_selection_and_immutable_config(tmp_path):
    (tmp_path / 'requirements.txt').write_text('pytest==8.3.3')
    (tmp_path / 'pytest.ini').write_text('[pytest]\ntestpaths = tests\n')
    assert runtime.register(str(tmp_path))['type'] == 'pytest'
    assert 'pytest.ini' in autofix.snapshot(tmp_path)
    assert not autofix.editable('pytest.ini')


def test_real_pytest_pass_failure_and_empty(tmp_path):
    if os.getenv('QA_PYTEST_INTEGRATION') != '1':
        pytest.skip('Requires prepared vibeqa-pytest:1 image')
    (tmp_path / 'requirements.txt').write_text('')
    (tmp_path / 'pytest.ini').write_text('[pytest]\n')
    (tmp_path / 'tests').mkdir()
    test = tmp_path / 'tests/test_value.py'
    test.write_text('def test_value():\n    assert 1 == 1\n')
    result = autofix.test_copy(tmp_path)
    assert result['state'] == 'passed', result
    test.write_text('def test_value():\n    assert 1 == 2\n')
    result = autofix.test_copy(tmp_path)
    assert result['state'] == 'failed', result
    test.write_text('')
    result = autofix.test_copy(tmp_path)
    assert result['state'] == 'no_tests', result
