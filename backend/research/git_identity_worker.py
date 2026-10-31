"""Fixed internal metadata CLI; raw Git output is never emitted or persisted.

Its parent owns the wall-clock deadline and bounded process-tree cleanup.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid


def _job_api():
    """The fixed collector's Windows containment, not a command runner API."""
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                    ('maximum', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                    ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                    ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

    class Accounting(ctypes.Structure):
        _fields_ = [('user', ctypes.c_int64), ('kernel', ctypes.c_int64),
                    ('period_user', ctypes.c_int64), ('period_kernel', ctypes.c_int64),
                    ('faults', wintypes.DWORD), ('total', wintypes.DWORD),
                    ('active', wintypes.DWORD), ('terminated', wintypes.DWORD)]

    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    api.OpenJobObjectW.restype = wintypes.HANDLE
    api.GetCurrentProcess.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.c_void_p]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    return ctypes, api, ExtendedLimits, Accounting


def _create_job():
    ctypes, api, limits_type, _ = _job_api()
    name = 'Local\\graphrag-git-identity-' + uuid.uuid4().hex
    handle = api.CreateJobObjectW(None, name)
    if not handle:
        raise OSError('GIT_IDENTITY_CONTAINMENT_UNAVAILABLE')
    limits = limits_type()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
    if not api.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        api.CloseHandle(handle)
        raise OSError('GIT_IDENTITY_CONTAINMENT_UNAVAILABLE')
    return handle, name


def _join_job(name):
    _, api, _, _ = _job_api()
    handle = api.OpenJobObjectW(0x0001, False, name)  # JOB_OBJECT_ASSIGN_PROCESS
    if not handle:
        return False
    try:
        return bool(api.AssignProcessToJobObject(handle, api.GetCurrentProcess()))
    finally:
        api.CloseHandle(handle)


def _stop_job(handle, deadline):
    ctypes, api, _, accounting_type = _job_api()
    try:
        if not api.TerminateJobObject(handle, 1):
            return False
        while True:
            counts = accounting_type()
            if not api.QueryInformationJobObject(handle, 1, ctypes.byref(counts), ctypes.sizeof(counts), None):
                return False
            if counts.active == 0:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.01, remaining))
    finally:
        api.CloseHandle(handle)


def collect(root):
    def run(*args):
        return subprocess.run(['git', '-C', root, *args], capture_output=True,
                              check=True, close_fds=True).stdout

    commit = run('rev-parse', 'HEAD').decode('ascii').strip()
    if re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit) is None:
        raise ValueError('GIT_IDENTITY_INVALID_COMMIT')
    dirty = run('diff', '--binary', 'HEAD')
    status = run('status', '--porcelain', '--untracked-files=all')
    return {'commit': commit, 'tracked_diff_sha256': hashlib.sha256(dirty).hexdigest(),
            'status_inventory_sha256': hashlib.sha256(status).hexdigest(),
            'untracked_content_in_diff_hash': False, 'loaded_runtime_identity': 'UNKNOWN'}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    try:
        result = collect(args[0])
    except (OSError, ValueError, subprocess.CalledProcessError):
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0


def owned_main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if os.name == 'nt':
        if len(args) != 2 or not _join_job(args[1]):
            return 2
        args = args[:1]
    return main(args)


if __name__ == '__main__':
    sys.exit(owned_main())
