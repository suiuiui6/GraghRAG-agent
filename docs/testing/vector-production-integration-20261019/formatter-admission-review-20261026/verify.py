"""Independent, synthetic scalar wiring checks; never opens a production DB."""
import hashlib, importlib.util, json, math, pathlib, struct, sys, tarfile, tomllib
from datetime import datetime, timezone
OUT = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
DERIVED = pathlib.Path('D:/graghRAG-agent')
relative = ['backend/vector_numeric.py', 'backend/sqlite_vector_store.py',
 'backend/native/vector_numeric/Cargo.toml', 'backend/native/vector_numeric/Cargo.lock',
 'backend/native/vector_numeric/rust-toolchain.toml', 'backend/native/vector_numeric/src/main.rs',
 'backend/native/vector_numeric/build.py', 'backend/native/vector_numeric/build-receipt.json',
 'backend/native/vector_numeric/bin/x86_64-pc-windows-msvc/approved-build.json',
 'backend/native/vector_numeric/bin/x86_64-pc-windows-msvc/vector-numeric-bridge.exe',
 'docs/design/2026-10-19-vector-production-integration.md',
 'docs/contracts/2026-10-14-vector-ingress-semantics.md']
evidence = ['.tmp/vector-bridge-review-20261020/REVIEW.md',
 '.tmp/vector-bridge-review-20261020/chroma-metadata-commit.rs',
 '.tmp/vector-bridge-review-20261020/chroma-metadata-api.rs',
 '.tmp/vector-bridge-review-20261020/chroma-Cargo.lock',
 '.tmp/vector-bridge-review-20261020/serde-derive-enum-untagged.rs',
 '.tmp/vector-bridge-review-20261020/serde-private-de.rs',
 '.tmp/vector-formatter-20261020/upstream/chroma-python-rust.py',
 '.tmp/vector-formatter-20261020/upstream/chroma-sqlite-log.rs',
 '.tmp/vector-formatter-20261020/upstream/chroma-bindings.rs']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
before = {str(ROOT / p): sha(ROOT / p) for p in relative}
before.update({str(DERIVED / p): sha(DERIVED / p) for p in evidence})
registry = pathlib.Path('C:/Users/14156/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f')
critical = {'serde_json-1.0.149':['src/ser.rs','src/de.rs','src/value/de.rs'],
 'zmij-1.0.21':['src/lib.rs'], 'serde_core-1.0.228':['src/de/impls.rs']}
lock = tomllib.loads((ROOT/'backend/native/vector_numeric/Cargo.lock').read_text())
source_checks = {}
for package, paths in critical.items():
    entry = next(p for p in lock['package'] if p['name']+'-'+p['version']==package)
    archive = DERIVED/'.tmp/vector-formatter-20261020/upstream'/(package+'.crate')
    assert sha(archive)==entry['checksum']
    before[str(archive)] = sha(archive)
    with tarfile.open(archive) as bundle:
        for part in paths:
            path = registry/package/part
            assert bundle.extractfile(package+'/'+part).read()==path.read_bytes()
            before[str(path)] = sha(path)
            source_checks[str(path)] = 'byte-identical to archive matching locked checksum'
spec = importlib.util.spec_from_file_location('independent_numeric', ROOT / relative[0])
numeric = importlib.util.module_from_spec(spec)
spec.loader.exec_module(numeric)
binary = numeric._verified_binary()
rows=[]
def check(op, x, expected):
    actual = getattr(numeric, op)(x)
    assert actual == expected, (op, x, actual, expected)
    rows.append({'op':op, 'input':x.hex() if type(x) is float else str(x),
                 'tag':actual[0], 'value':actual[1].hex() if type(actual[1]) is float else str(actual[1])})
for value in [-(1<<63), -1, 0, (1<<63)-1]: check('record_ingress', value, ('i64', value))
for value in [0.0, -0.0, 1.0, -1.0]: check('record_ingress', value, ('f64', 0.0 if value==0 else value))
assert math.copysign(1, numeric.record_ingress(-0.0)[1]) == 1
check('record_ingress', math.nextafter(float(1<<63), 0.0), ('f64', float(1<<63)))
check('record_ingress', 1<<63, ('f64', float(1<<63)))
check('record_ingress', (1<<64)+1, ('f64', float(1<<64)))
for value in [0, (1<<63)-1, 1<<63, (1<<64)-1]: check('parse', json.dumps(value), ('u64',value))
check('parse', json.dumps(-(1<<63)), ('i64', -(1<<63)))
check('parse', json.dumps(-0.0), ('f64', -0.0))
assert math.copysign(1,numeric.parse(json.dumps(-0.0))[1]) == -1
check('parse', str(10**308), ('f64', 1e308))
for token in [str(10**309), 'NaN', 'Infinity']:
    try: numeric.parse(token)
    except ValueError: rows.append({'op':'parse','input':token[:20], 'length':len(token),'rejected':True})
    else: raise AssertionError('missing rejection')
after = {p:sha(pathlib.Path(p)) for p in before}
assert before == after
report = {'utc':datetime.now(timezone.utc).isoformat(), 'python':sys.version,
 'scope':'Windows scalar bridge only; no Chroma execution, no all-domain statistical claim',
 'binary':str(binary),'inputs_sha256':before,'registry_source_checks':source_checks,'unchanged':True,'checks':rows,
 'actual_wheel_features':'PENDING authoritative build/feature provenance; prior finite probes are behavior evidence only'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks':len(rows),'unchanged':True,'binary_sha256':sha(binary)}))
