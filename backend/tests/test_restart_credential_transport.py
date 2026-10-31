"""Unit checks for secret-free child process diagnostics, not lifecycle evidence."""
import json
import subprocess
from types import SimpleNamespace

import pytest
from backend.tests import test_vector_http_lifecycle as subject


def test_restart_credentials_are_delivered_without_command_arguments(monkeypatch, tmp_path):
    credential = 'synthetic-credential-not-a-command-argument'
    headers = {'Authorization': 'Bearer ' + credential}
    observed = {}

    def boundary(command, **options):
        observed.update(command=command, options=options)
        return subprocess.CompletedProcess(command, 0, 'CHILD_RESULT={"status":200,"body":{}}\n', '')

    monkeypatch.setattr(subject.subprocess, 'run', boundary)
    result = subject.child_http_query(SimpleNamespace(root=tmp_path),
        SimpleNamespace(model_profile=subject.PROFILE), headers, 'fixture-doc', 'http://127.0.0.1:1')
    assert result == {'status': 200, 'body': {}}
    assert credential not in str(observed['command'])
    assert json.loads(observed['options']['input'])['headers'] == headers


def test_restart_timeout_diagnostic_does_not_contain_credentials(monkeypatch, tmp_path):
    credential = 'synthetic-timeout-credential-not-for-diagnostics'

    def boundary(command, **options):
        raise subprocess.TimeoutExpired(command, options['timeout'])

    monkeypatch.setattr(subject.subprocess, 'run', boundary)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        subject.child_http_query(SimpleNamespace(root=tmp_path),
            SimpleNamespace(model_profile=subject.PROFILE), {'Authorization': 'Bearer ' + credential},
            'fixture-doc', 'http://127.0.0.1:1')
    assert credential not in str(caught.value)
