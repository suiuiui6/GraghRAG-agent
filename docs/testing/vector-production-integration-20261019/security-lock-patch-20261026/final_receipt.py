import concurrent.futures,hashlib,importlib.metadata,json,pathlib,re,sqlite3,tomllib
import numpy
ROOT=pathlib.Path(__file__).resolve().parent
OLD=pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Lib/site-packages')
NEW=ROOT/'.venv/Lib/site-packages'
copied=json.loads((ROOT/'copied-unchanged-files.json').read_text(encoding='utf-8'))
changes={}
def verify(item):
    rel,digest=item
    bad={}
    for label,base in [('old',OLD),('new',NEW)]:
        actual=hashlib.file_digest((base/rel).open('rb'),'sha256').hexdigest()
        if actual!=digest:bad[label+':'+rel]=actual
    return bad
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for bad in pool.map(verify,copied.items()):changes.update(bad)
assert not changes,changes
lock=tomllib.loads((ROOT/'backend/uv.lock').read_text(encoding='utf-8'))
registry={p['name']:p['version'] for p in lock['package'] if 'registry' in p.get('source',{})}
expected=json.loads(pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/final-runtime-receipt.json').read_text(encoding='utf-8'))
original={p['name']:p['version'] for p in tomllib.loads(pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/uv.lock').read_text(encoding='utf-8'))['package'] if 'registry' in p.get('source',{})}
diff={p:{'old':original.get(p),'new':v} for p,v in registry.items() if original.get(p)!=v}
installed={re.sub(r'[-_.]+','-',p.metadata['Name'].lower()):p.version for p in importlib.metadata.distributions()}
expected_installed=expected['installed'].copy()
expected_installed.update({'filelock':'4.2.1','opentelemetry-api':'1.45.1','setuptools':'84.1.0'})
assert installed==expected_installed,{'missing':set(expected_installed)-set(installed),'extra':set(installed)-set(expected_installed),'mismatch':{p:(expected_installed[p],installed[p]) for p in set(installed)&set(expected_installed) if installed[p]!=expected_installed[p]}}
missing_or_mismatch={p:{'lock':v,'installed':installed.get(p)} for p,v in registry.items() if p in installed and installed[p]!=v}
assert not missing_or_mismatch,missing_or_mismatch
assert len(installed)==159,(len(installed),installed)
assert sqlite3.sqlite_version=='3.54.0'
assert numpy.__version__=='2.5.4'
conn=sqlite3.connect(':memory:');conn.execute('create table x(v blob)');a=numpy.array([1,2,3],dtype=numpy.float32);conn.execute('insert into x values(?)',(a.tobytes(),));assert numpy.array_equal(numpy.frombuffer(conn.execute('select v from x').fetchone()[0],dtype=numpy.float32),a)
receipt={'python':__import__('sys').executable,'sqlite':sqlite3.sqlite_version,'numpy':numpy.__version__,'lock_diff':diff,'registry_count':len(registry),'installed_count':len(installed),'installed':installed,'copied_files_verified_before_after':len(copied),'unchanged_file_drift':changes,'hashes':{p.name:hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in (ROOT/'backend').iterdir() if p.is_file()},'limitation':'Verified unchanged installed payload cloned; not from-zero full package reinstall. Windows only.'}
(ROOT/'runtime-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in receipt.items() if k!='installed'},indent=2))
