"""Real Git and owned subprocess regressions for optional identity metadata."""
import hashlib
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from backend.research import local_scope_v2 as module
from backend.research import git_identity_worker as worker

UNAVAILABLE = {'status': 'GIT_IDENTITY_UNAVAILABLE', 'loaded_runtime_identity': 'UNKNOWN'}


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                          check=True, timeout=10).stdout


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, 'init')
    (tmp_path / 'tracked').write_bytes(b'original\n')
    git(tmp_path, 'add', 'tracked')
    git(tmp_path, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    (tmp_path / 'tracked').write_bytes(b'changed\x00binary\n')
    (tmp_path / 'untracked').write_bytes(b'private untracked body')
    return tmp_path


def test_exact_original_three_command_bytes(repository):
    expected = {'commit': git(repository, 'rev-parse', 'HEAD').decode('ascii').strip(),
                'tracked_diff_sha256': hashlib.sha256(git(repository, 'diff', '--binary', 'HEAD')).hexdigest(),
                'status_inventory_sha256': hashlib.sha256(git(repository, 'status', '--porcelain', '--untracked-files=all')).hexdigest(),
                'untracked_content_in_diff_hash': False, 'loaded_runtime_identity': 'UNKNOWN'}
    assert module._git_identity(repository) == expected
    (repository / 'untracked').write_bytes(b'different private body')
    assert module._git_identity(repository) == expected
    (repository / 'tracked').write_bytes(b'new tracked bytes\n')
    current = module._git_identity(repository)
    assert current['tracked_diff_sha256'] != expected['tracked_diff_sha256']
    assert current['tracked_diff_sha256'] == hashlib.sha256(git(repository, 'diff', '--binary', 'HEAD')).hexdigest()


def test_nonrepository_is_wholly_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))
    assert module._git_identity(tmp_path) == UNAVAILABLE


def test_missing_git_is_wholly_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', '')
    assert module._git_identity(tmp_path) == UNAVAILABLE


def running(pid):
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 258
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_shared_deadline_cleans_real_inherited_output_descendant(tmp_path, monkeypatch):
    """The helper and its child use ordinary inherited stdout/stderr handles."""
    pids = tmp_path / 'pids.json'
    helper = tmp_path / 'owned_helper.py'
    worker = Path(module.__file__).with_name('git_identity_worker.py')
    helper.write_text('import importlib.util,json,os,subprocess,sys,time\n'
        f'spec=importlib.util.spec_from_file_location("worker",{str(worker)!r})\n'
        'w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)\n'
        'if os.name=="nt" and not w._join_job(sys.argv[2]): sys.exit(2)\n'
        'child=subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(4)"])\n'
        'open(sys.argv[1],"w").write(json.dumps([os.getpid(),child.pid]))\n'
        'time.sleep(3)\n', encoding='utf-8')
    real_popen = subprocess.Popen
    owned = []

    def factory(args, **kwargs):
        # Only substitute collection, never the owned-tree cleanup command.
        if args[0] == 'git' or (len(args) > 2 and str(args[2]).endswith('git_identity_worker.py')):
            args = [sys.executable, '-B', str(helper), str(pids), *args[4:]]
        proc = real_popen(args, **kwargs)
        owned.append(proc)
        return proc

    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 0.5, raising=False)
    monkeypatch.setattr(module.subprocess, 'Popen', factory)
    start = time.monotonic()
    try:
        report = module._git_identity(tmp_path)
        elapsed = time.monotonic() - start
        assert elapsed < 2.5, elapsed
        assert report == UNAVAILABLE
        assert pids.exists(), 'real helper must have started'
        identities = json.loads(pids.read_text())
        assert len(identities) == 2
        assert not any(running(pid) for pid in identities), identities
    finally:
        # Every fixture self-expires. Cleanup is restricted to owned live roots.
        for proc in owned:
            if proc.poll() is None:
                if os.name == 'nt':
                    real_popen(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait(timeout=2)
                else:
                    proc.kill()
                proc.wait(timeout=2)


def controlled_worker(tmp_path, monkeypatch, *, slow='', fail='', delay=0, large=False,
                      orphan='', invalid_commit=False):
    """Run the real worker and real helper processes; replace only Git launch."""
    helper = tmp_path / 'git_helper.py'
    phases = tmp_path / 'phases.jsonl'
    helper.write_text(
        'import json,os,subprocess,sys,time\n'
        'phase=sys.argv[1]\n'
        f'with open({str(phases)!r},"a") as f: f.write(json.dumps([phase,os.getpid()])+"\\n")\n'
        f'if {orphan!r} and phase=="status":\n'
        ' kw={}\n'
        f' if {orphan!r}=="no-pipe": kw=dict(stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
        ' child=subprocess.Popen([sys.executable,"-B","-c","import time;time.sleep(4)"],**kw)\n'
        f' with open({str(phases)!r},"a") as f: f.write(json.dumps(["descendant",child.pid])+"\\n")\n'
        f'time.sleep(4 if phase=={slow!r} else {delay!r})\n'
        'data=("a"*40+"\\n").encode() if phase=="rev-parse" else b"private-sentinel\\x00"\n'
        f'if {invalid_commit!r} and phase=="rev-parse": data=b"private-invalid-commit"*10000\n'
        f'if {large!r} and phase!="rev-parse":\n'
        ' import threading\n'
        ' t=threading.Thread(target=lambda:sys.stderr.buffer.write(b"private-stderr"*10000))\n'
        ' t.start()\n'
        ' sys.stdout.buffer.write(data*10000)\n'
        ' t.join()\n'
        'else: sys.stdout.buffer.write(data)\n'
        f'sys.exit(7 if phase=={fail!r} else 0)\n', encoding='utf-8')
    driver = tmp_path / 'worker_driver.py'
    worker = Path(module.__file__).with_name('git_identity_worker.py')
    driver.write_text(
        'import importlib.util,subprocess,sys\n'
        f'spec=importlib.util.spec_from_file_location("fixed_worker",{str(worker)!r})\n'
        'w=importlib.util.module_from_spec(spec)\n'
        'spec.loader.exec_module(w)\n'
        'real=subprocess.Popen\n'
        'def factory(args,**kw):\n'
        f' return real([sys.executable,"-B",{str(helper)!r},args[3]],**kw)\n'
        'w.subprocess.Popen=factory\n'
        'sys.exit(w.owned_main(sys.argv[1:]))\n', encoding='utf-8')
    real_popen = subprocess.Popen

    def factory(args, **kwargs):
        if len(args) > 2 and str(args[2]).endswith('git_identity_worker.py'):
            args = [sys.executable, '-B', str(driver), *args[3:]]
        return real_popen(args, **kwargs)

    monkeypatch.setattr(module.subprocess, 'Popen', factory)
    return phases


@pytest.mark.parametrize('phase', ['rev-parse', 'diff', 'status'])
def test_each_command_timeout_discards_complete_and_partial_identity(tmp_path, monkeypatch, phase):
    phases = controlled_worker(tmp_path, monkeypatch, slow=phase)
    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 2.0)
    start = time.monotonic()
    assert module._git_identity(tmp_path) == UNAVAILABLE
    assert time.monotonic() - start < 4.5
    records = [json.loads(line) for line in phases.read_text().splitlines()]
    assert records[-1][0] == phase, records
    assert not any(running(pid) for _, pid in records)


@pytest.mark.parametrize('phase', ['rev-parse', 'diff', 'status'])
def test_each_command_nonzero_discards_complete_and_partial_identity(tmp_path, monkeypatch, phase):
    phases = controlled_worker(tmp_path, monkeypatch, fail=phase)
    report = module._git_identity(tmp_path)
    assert report == UNAVAILABLE
    assert 'private-sentinel' not in json.dumps(report)
    records = [json.loads(line) for line in phases.read_text().splitlines()]
    assert records[-1][0] == phase, records
    assert not any(running(pid) for _, pid in records)


def test_three_commands_share_one_wall_clock_budget(tmp_path, monkeypatch):
    phases = controlled_worker(tmp_path, monkeypatch, delay=0.8)
    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 2.0)
    start = time.monotonic()
    assert module._git_identity(tmp_path) == UNAVAILABLE
    assert time.monotonic() - start < 4.5
    records = [json.loads(line) for line in phases.read_text().splitlines()]
    assert len(records) >= 2, records
    assert not any(running(pid) for _, pid in records)


def test_large_simultaneous_git_stdout_stderr_preserves_complete_hashes(tmp_path, monkeypatch):
    controlled_worker(tmp_path, monkeypatch, large=True)
    report = module._git_identity(tmp_path)
    digest = hashlib.sha256(b'private-sentinel\x00' * 10000).hexdigest()
    assert report == {'commit': 'a' * 40, 'tracked_diff_sha256': digest,
                      'status_inventory_sha256': digest,
                      'untracked_content_in_diff_hash': False,
                      'loaded_runtime_identity': 'UNKNOWN'}
    assert 'private-sentinel' not in json.dumps(report)


@pytest.mark.parametrize('orphan', ['pipe', 'no-pipe'])
def test_immediate_helper_exit_does_not_escape_owned_containment(tmp_path, monkeypatch, orphan):
    phases = controlled_worker(tmp_path, monkeypatch, orphan=orphan)
    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 2.0)
    start = time.monotonic()
    report = module._git_identity(tmp_path)
    if orphan == 'pipe':
        assert report == UNAVAILABLE
    else:
        assert report['commit'] == 'a' * 40
    assert time.monotonic() - start < 4.5
    records = [json.loads(line) for line in phases.read_text().splitlines()]
    assert records[-1][0] == 'descendant', records
    assert not any(running(pid) for _, pid in records), records


def test_invalid_large_revparse_never_reaches_temporary_json(tmp_path, monkeypatch):
    phases = controlled_worker(tmp_path, monkeypatch, invalid_commit=True)
    captured = []
    real_temporary_file = module.tempfile.TemporaryFile

    class InspectOnClose:
        def __enter__(self):
            self.file = real_temporary_file()
            return self.file

        def __exit__(self, *exc):
            self.file.seek(0)
            captured.append(self.file.read())
            self.file.close()

    monkeypatch.setattr(module.tempfile, 'TemporaryFile', InspectOnClose)
    assert module._git_identity(tmp_path) == UNAVAILABLE
    assert captured == [b'']
    assert [json.loads(line)[0] for line in phases.read_text().splitlines()] == ['rev-parse']


def test_worker_collect_and_main_use_exact_real_git_hashes(repository, capsys):
    expected = module._git_identity(repository)
    assert worker.collect(str(repository)) == expected
    assert worker.main([str(repository)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == expected
    assert output.err == ''
    assert 'private untracked' not in output.out


@pytest.mark.parametrize('argv', [[], ['one', 'two']])
def test_worker_argument_error_is_silent(argv, capsys):
    assert worker.main(argv) == 2
    assert capsys.readouterr() == ('', '')


def test_worker_real_git_error_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))
    assert worker.main([str(tmp_path)]) == 2
    monkeypatch.setenv('PATH', '')
    assert worker.main([str(tmp_path)]) == 2
    assert capsys.readouterr() == ('', '')


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job containment boundary')
def test_worker_cannot_start_git_without_its_private_job(tmp_path, capsys):
    assert worker.owned_main([]) == 2
    assert worker.owned_main([str(tmp_path), 'Local\\nonexistent-git-identity-fixture-job']) == 2
    assert capsys.readouterr() == ('', '')


def test_worker_launch_failure_returns_wholly_unknown_and_closes_job(tmp_path, monkeypatch):
    stopped = []
    original = module._stop_job

    def stop(handle, deadline):
        result = original(handle, deadline)
        stopped.append(result)
        return result

    def fail(*args, **kwargs):
        raise OSError('private exception sentinel')

    monkeypatch.setattr(module, '_stop_job', stop)
    monkeypatch.setattr(module.subprocess, 'Popen', fail)
    assert module._git_identity(tmp_path) == UNAVAILABLE
    if os.name == 'nt':
        assert stopped == [True]


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job containment boundary')
def test_job_creation_failure_never_launches_git(tmp_path, monkeypatch):
    def fail():
        raise OSError('private containment exception sentinel')

    monkeypatch.setattr(module, '_create_job', fail)
    assert module._git_identity(tmp_path) == UNAVAILABLE


def test_cleanup_failure_cannot_leave_a_success_identity(repository, monkeypatch):
    original = module._stop_identity_worker

    def cleanup(*args):
        original(*args)
        raise OSError('private cleanup exception sentinel')

    monkeypatch.setattr(module, '_stop_identity_worker', cleanup)
    assert module._git_identity(repository) == UNAVAILABLE


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job cleanup error boundary')
def test_job_cleanup_oserror_still_boundedly_reaps_live_worker(tmp_path, monkeypatch):
    phases = controlled_worker(tmp_path, monkeypatch, slow='rev-parse')
    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 2.0)
    launch = module.subprocess.Popen
    stop_job = module._stop_job
    roots = []
    waits = []
    jobs = []
    live_at_failure = []

    def observe_launch(args, **kwargs):
        proc = launch(args, **kwargs)
        roots.append(proc)
        original_wait = proc.wait

        def wait(timeout=None):
            waits.append(timeout)
            return original_wait(timeout=timeout)

        proc.wait = wait
        return proc

    def fail_stop_job(handle, deadline):
        jobs.append(handle)
        live_at_failure.append(roots[0].poll() is None)
        # Close the real Job through its normal implementation even when the
        # injected API error propagates. Parent must still explicitly reap.
        try:
            raise OSError('private job cleanup exception sentinel')
        finally:
            stop_job(handle, deadline)

    monkeypatch.setattr(module.subprocess, 'Popen', observe_launch)
    monkeypatch.setattr(module, '_stop_job', fail_stop_job)
    start = time.monotonic()
    try:
        assert module._git_identity(tmp_path) == UNAVAILABLE
        assert time.monotonic() - start < 4.5
        assert live_at_failure == [True]
        assert len(waits) == 2, waits
        assert 0 < waits[-1] <= module.GIT_IDENTITY_CLEANUP_SECONDS
        assert roots[0].returncode is not None
        records = [json.loads(line) for line in phases.read_text().splitlines()]
        assert not any(running(pid) for _, pid in records)
    finally:
        for proc in roots:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=2)


def test_fixed_worker_is_explicitly_registered_with_only_cli_output():
    from backend.tests import test_error_handling_policy as policy
    relative = 'research/git_identity_worker.py'
    assert relative in policy.RESEARCH_CLI_ENTRYPOINTS
    tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    assert list(policy._library_print_lines(tree, True)) == []
    assert len(list(policy._library_print_lines(tree, False))) == 1


@pytest.mark.parametrize('body,code', [(b'{"commit":"partial"}', 0),
                                     (b'{', 0), (b'{}', 7), (b'x' * 4097, 0)])
def test_invalid_worker_result_never_promotes_partial_metadata(tmp_path, monkeypatch, body, code):
    real_popen = subprocess.Popen

    def factory(args, **kwargs):
        return real_popen([sys.executable, '-B', '-c',
                           f'import sys;sys.stdout.buffer.write({body!r});sys.exit({code})'], **kwargs)

    monkeypatch.setattr(module.subprocess, 'Popen', factory)
    assert module._git_identity(tmp_path) == UNAVAILABLE


def test_timeout_prepare_cli_keeps_every_research_gate_blocked(tmp_path, monkeypatch, capsys):
    from backend.tests.frozen_input_helpers import data_root
    controlled_worker(tmp_path, monkeypatch, slow='status')
    monkeypatch.setattr(module, 'GIT_IDENTITY_TIMEOUT_SECONDS', 2.0)
    assert module.main(['--root', str(data_root()), 'prepare-b0']) == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report['git'] == UNAVAILABLE
    assert report['collector_source_basis'] == 'CURRENT_MODULE_DIRECTORY_ON_DISK_NOT_LOADED_IDENTITY'
    assert report['collector_source_sha256'] == {
        'backend/research/' + file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in (Path(module.__file__), Path(worker.__file__))}
    assert report['adapter_sha256'] == {
        'backend/research/' + name + '.py': hashlib.sha256(
            (data_root() / 'backend/research' / (name + '.py')).read_bytes()).hexdigest()
        for name in ('gold_v2', 'scope_v2', 'source_mapping_v2', 'local_scope_v2')}
    assert report['status'] == 'BLOCKED_NOT_EXECUTED'
    assert report['api_execution'] == 'NOT_EXECUTED'
    assert report['scientific_stage'] == 'M2_OPEN'
    assert report['conditional_call_proposal']['authorized'] is False
    assert report['gates'] == {
        'gold_local_source_binding': 'PASS',
        'on_disk_production_freeze': ('PASS' if report['production_integrity']['all_match_freeze']
                                      else 'DRIFT_REQUIRES_REVIEW'),
        'runtime_identity': 'UNKNOWN', 'local_embedding_runtime_ready': 'UNKNOWN',
        'native_corpus_document_identity': 'UNKNOWN', 'index_coordinate_gate': 'UNVERIFIED',
        'production_source_selection': 'SOURCE_UNRESOLVED',
        'same_version_native_context_capture': 'NOT_CAPTURED',
        'prompt_and_request_envelope_freeze': 'NOT_CAPTURED',
        'call_graph_and_retry_bound': 'UNVERIFIED',
        'provider_transfer_authorization': 'NOT_GRANTED_FOR_THIS_BATCH',
        'redacted_export_and_original_mapping': 'NOT_PREPARED',
        'finite_batch_authorization': 'NOT_GRANTED_FOR_THIS_BATCH',
        'state_cache_session_plan': 'NOT_FROZEN',
        'human_gold_certification': 'PENDING_SEPARATE_REVIEW',
    }
    assert len(report['questions']) == 9
    assert all(q['status'] == 'NOT_RUN' and q['source_selection'] == 'SOURCE_UNRESOLVED'
               for q in report['questions'])
    assert captured.err == ''
    assert 'private-sentinel' not in captured.out
