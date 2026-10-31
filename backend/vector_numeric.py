"""Original serde formatter/default-parser bridge, with fail-closed package identity.

Only canonical Python JSON scalar tokens are an input contract for ``parse``.
The trusted installation directory and approval manifest must be read-only to the
service account. Build identity is not an OS-level sandbox or native audit.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import threading

_ROOT = Path(__file__).resolve().parent / 'native' / 'vector_numeric'
_TIMEOUT = 10.0
_SLOTS = threading.BoundedSemaphore(4)
_FEATURES = ['serde_json/std', 'zmij/default']
_SOURCE_FILES = ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', 'src/main.rs')
_TOKEN = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z', re.ASCII)


class NumericBridgeUnavailable(RuntimeError):
    """Safe operational failure; public adapters map it to storage_unavailable."""
    def __init__(self):
        super().__init__('numeric bridge unavailable')


def _target():
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        raise NumericBridgeUnavailable()
    if os.name == 'nt':
        return 'x86_64-pc-windows-msvc', 'vector-numeric-bridge.exe'
    if platform.system() == 'Linux':
        return 'x86_64-unknown-linux-gnu', 'vector-numeric-bridge'
    raise NumericBridgeUnavailable()


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_binary():
    try:
        target, name = _target()
        package = _ROOT / 'bin' / target
        binary = package / name
        manifest_path = package / 'approved-build.json'
        # Manifest is a small reviewed package file, never executable settings.
        with manifest_path.open('rb') as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise NumericBridgeUnavailable()
        manifest = json.loads(raw)
        expected = {name: _sha(binary)}
        expected.update({file: _sha(_ROOT / file) for file in _SOURCE_FILES})
        if (manifest.get('schema') != 1 or manifest.get('approved') is not True
                or manifest.get('target') != target
                or manifest.get('profile') != 'release'
                or manifest.get('features') != _FEATURES
                or manifest.get('files') != expected):
            raise NumericBridgeUnavailable()
        return binary
    except (OSError, ValueError, TypeError, AttributeError):
        raise NumericBridgeUnavailable() from None


def _exchange(request):
    # All callers construct <= 384 ASCII bytes. Never accept an arbitrary command.
    if not _SLOTS.acquire(timeout=_TIMEOUT):
        raise NumericBridgeUnavailable()
    process = None
    reader = None
    rows = []
    try:
        binary = _verified_binary()
        env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
        process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   cwd=str(binary.parent), env=env, shell=False,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        # <= 384 bytes fits supported platform anonymous pipe buffer. No batch
        # joins, unbounded communicate/capture, or threads writing caller input.
        process.stdin.write(request.encode('ascii'))
        process.stdin.close()

        def read_response():
            try:
                rows.append(process.stdout.read(65))
            except OSError:
                rows.append(b'')

        reader = threading.Thread(target=read_response, daemon=True)
        reader.start()
        reader.join(_TIMEOUT)
        if reader.is_alive():
            raise NumericBridgeUnavailable()
        if process.wait(timeout=_TIMEOUT) != 0 or not rows or len(rows[0]) > 64:
            raise NumericBridgeUnavailable()
        return rows[0]
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise NumericBridgeUnavailable() from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if reader is not None:
                reader.join(_TIMEOUT)
            for stream in (process.stdin, process.stdout):
                if stream is not None and not stream.closed:
                    stream.close()
        _SLOTS.release()


def _decode(row, error):
    if row in (b'err\tinvalid_filter\t-\n', b'err\tinvalid_input\t-\n'):
        raise ValueError(error)
    match = re.fullmatch(rb'ok\t(f64|i64|u64)\t([^\n\r\t]+)\n', row)
    if match is None:
        raise NumericBridgeUnavailable()
    tag, payload = match.groups()
    if tag == b'f64':
        if re.fullmatch(rb'[0-9a-f]{16}', payload) is None:
            raise NumericBridgeUnavailable()
        value = struct.unpack('>d', bytes.fromhex(payload.decode('ascii')))[0]
        if not math.isfinite(value):
            raise NumericBridgeUnavailable()
    else:
        if re.fullmatch(rb'-?(?:0|[1-9][0-9]{0,19})', payload) is None:
            raise NumericBridgeUnavailable()
        value = int(payload)
        if not (-(1 << 63) <= value < (1 << 63) if tag == b'i64' else 0 <= value < (1 << 64)):
            raise NumericBridgeUnavailable()
    return tag.decode('ascii'), value


def parse(token):
    """Replay original where default-parser path for Python json.dumps scalars."""
    if type(token) is not str or _TOKEN.fullmatch(token) is None:
        raise ValueError('invalid numeric filter')
    # Canonical json.dumps float tokens are short. A canonical integer with
    # >309 decimal digits is >=1e309: the original parser rejects as nonfinite.
    # This is a semantic rejection, not a record/batch size limit.
    if len(token.lstrip('-')) > 309:
        raise ValueError('invalid numeric filter')
    return _decode(_exchange('where\t' + token + '\n'), 'invalid numeric filter')


def record_ingress(value):
    """Typed Python i64/f64 -> original formatter -> parser -> SQLite zero.

    Integers outside i64 follow original PyO3 finite-f64 extraction. Stored
    values must never be passed here again during public readback.
    """
    if type(value) is int and -(1 << 63) <= value < (1 << 63):
        # Canonical i64 formatter/parser is the exact integer identity.
        return 'i64', value
    else:
        if type(value) not in (int, float):
            raise ValueError('invalid numeric record')
        try:
            number = float(value)
        except OverflowError:
            raise ValueError('invalid numeric record') from None
        if not math.isfinite(number):
            raise ValueError('invalid numeric record')
        request = 'record_f64\t' + struct.pack('>d', number).hex() + '\n'
    tag, number = _decode(_exchange(request), 'invalid numeric record')
    return tag, 0.0 if tag == 'f64' and number == 0.0 else number
