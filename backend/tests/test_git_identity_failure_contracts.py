"""Failure contracts for optional Git metadata, using owned OS resources."""
import ctypes
import json
import subprocess
import sys
import time

import pytest

from backend.research import git_identity_worker as worker
from backend.research import local_scope_v2 as scope

UNAVAILABLE = {'status': 'GIT_IDENTITY_UNAVAILABLE', 'loaded_runtime_identity': 'UNKNOWN'}



class _ObservedJobApi:
    """Observe successful real closes, without probing an invalid handle."""
    def __init__(self, api):
        self.api = api
        self.closed = []

    def __getattr__(self, key):
        return getattr(self.api, key)

    def CloseHandle(self, handle):
        result = self.api.CloseHandle(handle)
        self.closed.append((handle, bool(result)))
        return result


@pytest.mark.parametrize('rights', [0x0004, 0x0008])
def test_stop_job_without_terminate_or_query_rights_fails_and_closes_handle(rights, monkeypatch):
    """Real access-denied calls must fail closed and release the supplied handle."""
    owner, name = worker._create_job()
    ctypes_module, api, limits, accounting = worker._job_api()
    limited = api.OpenJobObjectW(rights, False, name)
    assert limited, ctypes.get_last_error()
    observed = _ObservedJobApi(api)
    monkeypatch.setattr(worker, '_job_api', lambda: (ctypes_module, observed, limits, accounting))
    try:
        started = time.monotonic()
        assert worker._stop_job(limited, started + 1) is False
        assert time.monotonic() - started < 2
        assert observed.closed == [(limited, True)]
        # The separate owner is unaffected by closing the limited handle.
        counts = accounting()
        assert api.QueryInformationJobObject(owner, 1, ctypes.byref(counts), ctypes.sizeof(counts), None)
        assert counts.active == 0
    finally:
        api.CloseHandle(owner)



@pytest.mark.parametrize('argv', [['worker'], ['worker', 'one', 'two']])
def test_worker_default_cli_argument_errors_are_silent(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    assert worker.main() == 2
    assert capsys.readouterr() == ('', '')


def test_owned_worker_default_arguments_reject_missing_job_silently(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['worker'])
    assert worker.owned_main() == 2
    assert capsys.readouterr() == ('', '')



@pytest.mark.parametrize('commit', [b'private-not-a-commit\n', b'\xff\xfe\n'])
def test_worker_rejects_real_helper_invalid_commit_before_diff(tmp_path, monkeypatch, capsys, commit):
    original_run = subprocess.run
    processes = []

    def run(args, **kwargs):
        result = original_run([sys.executable, '-B', '-c',
            f'import sys;sys.stdout.buffer.write({commit!r})'], **kwargs)
        processes.append((args, result.returncode))
        return result

    monkeypatch.setattr(worker.subprocess, 'run', run)
    with pytest.raises(ValueError):
        worker.collect(str(tmp_path))
    assert worker.main([str(tmp_path)]) == 2
    assert capsys.readouterr() == ('', '')
    assert len(processes) == 2
    assert all(args == ['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'] and code == 0
               for args, code in processes)


@pytest.mark.parametrize('observations,expired,expected', [(2, False, True), (1, True, False)])
def test_job_cleanup_accounting_delay_is_bounded_and_reaps_owned_child(
        tmp_path, monkeypatch, observations, expired, expected):
    """Inject delayed accounting, while terminate/close/reap use a real Job."""
    from pathlib import Path
    owner, name = worker._create_job()
    ctypes_module, api, limits, accounting = worker._job_api()
    driver = tmp_path / 'job_child.py'
    ready = tmp_path / 'ready'
    driver.write_text(
        'import importlib.util,sys,time\n'
        f'spec=importlib.util.spec_from_file_location("worker",{str(Path(worker.__file__))!r})\n'
        'w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)\n'
        'assert w._join_job(sys.argv[1])\n'
        f'open({str(ready)!r},"w").write("ready")\n'
        'time.sleep(10)\n', encoding='utf-8')
    child = subprocess.Popen([sys.executable, '-B', str(driver), name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    queries = []

    class DelayedAccounting(_ObservedJobApi):
        def QueryInformationJobObject(self, handle, kind, output, size, returned):
            result = api.QueryInformationJobObject(handle, kind, output, size, returned)
            assert result
            queries.append(True)
            if len(queries) <= observations:
                ctypes.cast(output, ctypes.POINTER(accounting)).contents.active = 1
            return result

    observed = DelayedAccounting(api)
    try:
        startup_deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < startup_deadline and child.poll() is None:
            time.sleep(0.01)
        assert ready.exists(), child.poll()
        monkeypatch.setattr(worker, '_job_api', lambda: (ctypes_module, observed, limits, accounting))
        started = time.monotonic()
        result = worker._stop_job(owner, started - 0.01 if expired else started + 1)
        assert result is expected
        assert time.monotonic() - started < 2
        assert len(queries) == (1 if expired else observations + 1)
        assert child.wait(timeout=2) == 1
        assert observed.closed == [(owner, True)]
    finally:
        if (owner, True) not in observed.closed:
            api.TerminateJobObject(owner, 1)
            api.CloseHandle(owner)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=2)
@pytest.mark.parametrize('coordinates,code,status', [([], 0, 'UNIQUE_EXACT_TEXT_MATCH'),
    (['--stored-start', '7', '--stored-end', '13'], 0, 'EXACT_STORED_SPAN'),
    (['--stored-start', '7'], 2, 'LOCAL_VALIDATION_FAILED')])
def test_local_map_cli_coordinate_contract_is_sanitized(tmp_path, capsys, coordinates, code, status):
    source = 'prefix target suffix'
    (tmp_path / 'source.txt').write_text(source, encoding='utf-8')
    (tmp_path / 'chunk.txt').write_text('target', encoding='utf-8')
    result = scope.main(['--root', str(tmp_path), 'map', '--source', 'source.txt',
                         '--chunk-file', 'chunk.txt', *coordinates])
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert result == code
    assert report['status'] == status
    assert captured.err == ''
    assert source not in captured.out
    if code == 2:
        assert report == {'status': 'LOCAL_VALIDATION_FAILED', 'api_execution': 'NOT_EXECUTED'}
    else:
        assert report['resolved_span'] == [7, 13]
        assert report['stored_span_verified'] is bool(coordinates)


def test_job_allocation_failure_is_explicit_without_configuring_an_invalid_handle(monkeypatch):
    ctypes_module, api, limits, accounting = worker._job_api()
    configured = []

    class AllocationDenied:
        def CreateJobObjectW(self, security, name):
            return None

        def SetInformationJobObject(self, *args):
            configured.append(args)
            raise AssertionError('Cannot configure an unallocated Job')

    monkeypatch.setattr(worker, '_job_api', lambda: (ctypes_module, AllocationDenied(), limits, accounting))
    with pytest.raises(OSError, match='^GIT_IDENTITY_CONTAINMENT_UNAVAILABLE$'):
        worker._create_job()
    assert configured == []


def test_job_configuration_access_denied_closes_only_the_new_restricted_handle(monkeypatch):
    owner, name = worker._create_job()
    ctypes_module, api, limits, accounting = worker._job_api()
    limited = api.OpenJobObjectW(0x0004, False, name)
    assert limited

    class RestrictedAllocation(_ObservedJobApi):
        def CreateJobObjectW(self, security, requested_name):
            return limited

    observed = RestrictedAllocation(api)
    try:
        monkeypatch.setattr(worker, '_job_api', lambda: (ctypes_module, observed, limits, accounting))
        with pytest.raises(OSError, match='^GIT_IDENTITY_CONTAINMENT_UNAVAILABLE$'):
            worker._create_job()
        assert observed.closed == [(limited, True)]
        counts = accounting()
        assert api.QueryInformationJobObject(owner, 1, ctypes.byref(counts), ctypes.sizeof(counts), None)
        assert counts.active == 0
    finally:
        api.CloseHandle(owner)
