import pytest


@pytest.fixture(autouse=True)
def no_real_credentials_in_unit_tests(monkeypatch):
    monkeypatch.setenv('QA_GITHUB_TOKEN', 'unit-test-placeholder')
