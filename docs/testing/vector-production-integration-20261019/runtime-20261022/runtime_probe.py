import base64, csv, ctypes, hashlib, importlib.metadata, io, json, pathlib, sqlite3, sys, tomllib
import numpy as np
import pytest

root=pathlib.Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
lock=tomllib.loads((root/'uv.lock').read_text())
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
locked_all={canonicalize_name(p['name']):p['version'] for p in lock['package'] if 'registry' in p.get('source',{})}
requirement_text=(root/'windows-requirements.txt').read_text().replace('\\\n',' ')
expected={}
skipped={}
for line in requirement_text.splitlines():
    line=line.strip()
    if not line or line.startswith('#'):continue
    requirement=Requirement(line.split('--hash=',1)[0].strip())
    name=canonicalize_name(requirement.name)
    (expected if requirement.marker is None or requirement.marker.evaluate() else skipped)[name]=locked_all[name]
locked=expected
distributions=list(importlib.metadata.distributions())
installed={canonicalize_name(d.metadata['Name']):d.version for d in distributions}
mismatch={k:{'expected':v,'actual':installed.get(k)} for k,v in locked.items() if installed.get(k)!=v}
extras={k:v for k,v in installed.items() if k not in locked and k!='langextract'}
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p];kernel.GetModuleHandleW.restype=ctypes.c_void_p
kernel.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint];kernel.GetModuleFileNameW.restype=ctypes.c_uint
buffer=ctypes.create_unicode_buffer(32768)
handle=kernel.GetModuleHandleW('sqlite3.dll')
assert handle and kernel.GetModuleFileNameW(handle,buffer,len(buffer))
dll=pathlib.Path(buffer.value).resolve()
assert dll== (root.parent/'vector-runtime-20261020/derived/python/DLLs/sqlite3.dll').resolve(), dll
assert sha(dll)=='5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656'
assert sqlite3.sqlite_version=='3.54.0' and np.__version__==locked['numpy']
conn=sqlite3.connect(':memory:');conn.execute('create table vectors(id text primary key, embedding blob)')
vector=np.asarray([1.,2.,3.],dtype='<f4');conn.execute('insert into vectors values (?,?)',('a',vector.tobytes()))
assert np.array_equal(np.frombuffer(conn.execute('select embedding from vectors where id=?',('a',)).fetchone()[0],dtype='<f4'),vector)
record_checks=[];record_errors=[]
for dist in distributions:
    checked=0
    for entry in csv.reader(io.StringIO(dist.read_text('RECORD') or '')):
        name,expected,size=entry
        if not expected: continue
        path=dist.locate_file(name)
        algorithm,encoded=expected.split('=',1)
        if not path.is_file():
            record_errors.append({'package':dist.metadata['Name'],'file':name,'error':'missing'});continue
        actual=base64.urlsafe_b64encode(hashlib.new(algorithm,path.read_bytes()).digest()).rstrip(b'=').decode()
        if actual!=encoded: record_errors.append({'package':dist.metadata['Name'],'file':name,'error':'hash mismatch'})
        checked+=1
    record_checks.append({'package':dist.metadata['Name'],'version':dist.version,'hashed_files_checked':checked})
receipt=dict(sys_executable=sys.executable,sys_version=sys.version,sys_prefix=sys.prefix,sys_base_prefix=sys.base_prefix,
    sqlite_version=sqlite3.sqlite_version,sqlite_dll=str(dll),sqlite_dll_sha256=sha(dll),numpy_version=np.__version__,pytest_version=pytest.__version__,
    pyproject_sha256=sha(root/'pyproject.toml'),uv_lock_sha256=sha(root/'uv.lock'),installed=installed,lock_version_mismatches=mismatch,
    installed_extras=extras,platform_applicable_registry=locked,platform_skipped_registry=skipped,record_checks=record_checks,record_errors=record_errors,sqlite_numpy_roundtrip=True,
    reused_cache='existing local artifact cache reused; uv pip --require-hashes --no-deps retained frozen export platform markers',
    audit_scope='runtime identity, lock versions, installed RECORD integrity, real SQLite+NumPy roundtrip; not a full native security audit')
(root/'runtime-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['sys_executable','sqlite_version','numpy_version','pytest_version','lock_version_mismatches','installed_extras','record_errors','sqlite_numpy_roundtrip']},indent=2))
assert not mismatch and not extras and not record_errors
