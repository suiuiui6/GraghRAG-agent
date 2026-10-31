"""Real native bridge contract and packaging fault tests."""
import importlib.util
from pathlib import Path
import math
import pytest

MODULE = Path(__file__).resolve().parents[1] / 'vector_numeric.py'
spec = importlib.util.spec_from_file_location('numeric_bridge_under_test', MODULE)
numeric = importlib.util.module_from_spec(spec)
spec.loader.exec_module(numeric)


def test_production_bridge_contract_exists():
    assert callable(getattr(numeric, 'record_ingress', None))
    assert callable(getattr(numeric, '_verified_binary', None))


def test_direct_record_formatter_regression():
    assert numeric.record_ingress(math.nextafter(2**63, 0.0)) == ('f64', float(2**63))
    assert numeric.record_ingress(0) == ('i64', 0)
    assert numeric.record_ingress(-(1 << 63)) == ('i64', -(1 << 63))
    assert numeric.record_ingress(-0.0) == ('f64', 0.0)
    assert math.copysign(1, numeric.record_ingress(-0.0)[1]) == 1


def test_where_keeps_u64_and_signed_zero():
    assert numeric.parse(str((1 << 64) - 1)) == ('u64', (1 << 64) - 1)
    assert math.copysign(1, numeric.parse('-0.0')[1]) == -1


@pytest.mark.parametrize('value', [True, None, 'SENSITIVE-MARKER', 1 << 1024, float('nan'), float('inf')])
def test_invalid_record_is_safe(value):
    with pytest.raises(ValueError) as exc:
        numeric.record_ingress(value)
    assert str(exc.value) == 'invalid numeric record'


@pytest.mark.parametrize('token', ['SENSITIVE-MARKER', '1\nwhere\t2', 'NaN', '9' * 10000])
def test_invalid_filter_is_safe(token):
    with pytest.raises(ValueError) as exc:
        numeric.parse(token)
    assert str(exc.value) == 'invalid numeric filter'


def test_wide_record_uses_original_typed_float_extraction():
    assert numeric.record_ingress(1 << 63) == ('f64', float(1 << 63))
    assert numeric.record_ingress(-(1 << 63) - 1)[0] == 'f64'


@pytest.fixture
def fault_package(tmp_path, monkeypatch):
    import json
    import shutil
    import subprocess
    native = tmp_path / 'native'
    native.mkdir()
    for file in numeric._SOURCE_FILES:
        destination = native / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(numeric._ROOT / file, destination)
    target, name = numeric._target()
    package = native / 'bin' / target
    package.mkdir(parents=True)
    source = tmp_path / 'fault.rs'
    source.write_text('''use std::io::{self,Read,Write};
fn main(){let mut s=String::new();io::stdin().read_to_string(&mut s).unwrap();
match s.trim(){
"hang"=>std::thread::sleep(std::time::Duration::from_secs(30)),
"flood"=>{let mut o=io::stdout().lock();loop{if o.write_all(&[120;1024]).is_err(){break;}}},
"crash"=>std::process::exit(7),
_=>println!("ok\\tu64\\t1")}}
''', encoding='utf-8')
    subprocess.run(['rustc', '+stable', str(source), '-O', '-o', str(package / name)], check=True, timeout=60)
    manifest = dict(schema=1, approved=True, target=target, profile='release',
                    features=numeric._FEATURES,
                    files={file: numeric._sha(native / file) for file in numeric._SOURCE_FILES})
    manifest['files'][name] = numeric._sha(package / name)
    approval = package / 'approved-build.json'
    approval.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(numeric, '_ROOT', native)
    return native, package / name, approval, manifest


@pytest.mark.parametrize('mutation', ['missing', 'unapproved', 'binary', 'source', 'lock', 'features', 'profile', 'manifest'])
def test_identity_rejection(fault_package, mutation):
    import json
    native, binary, approval, manifest = fault_package
    if mutation == 'missing': binary.unlink()
    elif mutation == 'binary': binary.write_bytes(binary.read_bytes() + b'tamper')
    elif mutation == 'source': (native / 'src/main.rs').write_text('tamper')
    elif mutation == 'lock': (native / 'Cargo.lock').write_text('tamper')
    elif mutation == 'manifest': approval.unlink()
    else:
        if mutation == 'unapproved': manifest['approved'] = False
        elif mutation == 'features': manifest['features'] = ['float_roundtrip']
        elif mutation == 'profile': manifest['profile'] = 'debug'
        approval.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(numeric.NumericBridgeUnavailable) as exc:
        numeric._verified_binary()
    assert str(exc.value) == 'numeric bridge unavailable'


@pytest.mark.parametrize('fault', ['hang', 'flood', 'crash'])
def test_real_child_fault_is_bounded_and_reaped(fault_package, monkeypatch, fault):
    import time
    import subprocess
    processes = []
    original = subprocess.Popen
    def launch(*args, **kwargs):
        assert kwargs['shell'] is False
        assert not any('SECRET' in key or key == 'PATH' for key in kwargs['env'])
        process = original(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(numeric.subprocess, 'Popen', launch)
    monkeypatch.setattr(numeric, '_TIMEOUT', 0.15)
    started = time.monotonic()
    with pytest.raises(numeric.NumericBridgeUnavailable):
        numeric._exchange(fault + '\n')
    assert time.monotonic() - started < 5
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert processes[0].stdin.closed and processes[0].stdout.closed


@pytest.mark.parametrize('row', [b'', b'ok\tf64\t7ff0000000000000\n', b'ok\tu64\t18446744073709551616\n',
                                b'ok\ti64\t9223372036854775808\n', b'ok\tu64\t-1\n',
                                b'ok\tu64\t1\nSENSITIVE-MARKER', b'err\tSENSITIVE-MARKER\t-\n'])
def test_malformed_response_cannot_escape(row):
    with pytest.raises(numeric.NumericBridgeUnavailable) as exc:
        numeric._decode(row, 'invalid numeric filter')
    assert str(exc.value) == 'numeric bridge unavailable'


def test_fault_recovery_releases_slot(fault_package, monkeypatch):
    normal_timeout=numeric._TIMEOUT
    monkeypatch.setattr(numeric, '_TIMEOUT', 0.1)
    with pytest.raises(numeric.NumericBridgeUnavailable):
        numeric._exchange('hang\n')
    # Fault injection targets the hung child; recovery uses production limits.
    monkeypatch.setattr(numeric, '_TIMEOUT', normal_timeout)
    assert numeric._decode(numeric._exchange('good\n'), 'invalid numeric filter') == ('u64', 1)


def test_concurrent_requests_share_bounded_slots(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    processes = []
    gate = threading.Lock()
    original = numeric.subprocess.Popen
    maximum = [0]
    def launch(*args, **kwargs):
        with gate:
            process = original(*args, **kwargs)
            processes.append(process)
            maximum[0] = max(maximum[0], sum(p.poll() is None for p in processes))
            return process
    monkeypatch.setattr(numeric.subprocess, 'Popen', launch)
    monkeypatch.setenv('BRIDGE_SECRET_MARKER', 'SYNTHETIC_PRIVATE_VALUE')
    with ThreadPoolExecutor(max_workers=12) as pool:
        values = list(pool.map(numeric.record_ingress, [float(n)+0.25 for n in range(24)]))
    assert values == [('f64', float(n)+0.25) for n in range(24)]
    assert len(processes) == 24
    assert maximum[0] <= 4
    assert all(p.poll() is not None and p.stdout.closed and p.stdin.closed for p in processes)


def test_slot_timeout_is_safe(monkeypatch):
    import threading
    monkeypatch.setattr(numeric, '_SLOTS', threading.BoundedSemaphore(1))
    monkeypatch.setattr(numeric, '_TIMEOUT', 0.01)
    numeric._SLOTS.acquire()
    try:
        with pytest.raises(numeric.NumericBridgeUnavailable):
            numeric.parse('1')
    finally:
        numeric._SLOTS.release()


def test_real_bridge_scalar_boundaries():
    import json
    import struct
    import sqlite3
    for value in (0.0, -0.0, 5e-324, -5e-324, 1.2345678901234567,
                  math.nextafter(2**63, 0.0), float.fromhex('0x1.fffffffffffffp+1023')):
        tag, replayed = numeric.record_ingress(value)
        assert tag == 'f64'
        db = sqlite3.connect(':memory:')
        try:
            db.execute('create table n(value real)')
            db.execute('insert into n values (?)', (replayed,))
            stored = db.execute('select value from n').fetchone()[0]
            assert struct.pack('>d', stored) == struct.pack('>d', replayed)
        finally:
            db.close()
        assert numeric.parse(json.dumps(value))[0] == 'f64'
    assert numeric.parse('1' + '0' * 308)[0] == 'f64'
    with pytest.raises(ValueError, match='invalid numeric filter'):
        numeric.parse('9' * 309)
