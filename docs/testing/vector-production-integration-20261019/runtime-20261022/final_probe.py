import hashlib,importlib.metadata,json,pathlib,re,sqlite3,sys,tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import numpy
root=pathlib.Path(__file__).resolve().parent; target=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend')
lock=tomllib.loads((target/'uv.lock').read_text()); all_locked={canonicalize_name(p['name']):p['version'] for p in lock['package'] if 'registry' in p.get('source',{})}
expected={}
for line in (root/'windows-requirements.txt').read_text().replace('\\\n',' ').splitlines():
 line=line.strip()
 if not line or line.startswith('#'):continue
 req=Requirement(line.split('--hash=',1)[0].strip())
 if req.marker is None or req.marker.evaluate():expected[canonicalize_name(req.name)]=all_locked[canonicalize_name(req.name)]
installed={canonicalize_name(d.metadata['Name']):d.version for d in importlib.metadata.distributions()}
mismatch={k:[v,installed.get(k)] for k,v in expected.items() if installed.get(k)!=v}; extras={k:v for k,v in installed.items() if k not in expected and k!='langextract'}
conn=sqlite3.connect(':memory:'); conn.execute('create table v(b blob)'); a=numpy.array([1,2,3],dtype='<f4');conn.execute('insert into v values(?)',(a.tobytes(),));assert numpy.array_equal(a,numpy.frombuffer(conn.execute('select b from v').fetchone()[0],dtype='<f4'))
receipt={'python':sys.executable,'python_version':sys.version,'sqlite':sqlite3.sqlite_version,'numpy':numpy.__version__,'registry_lock_count':len(all_locked),'windows_expected_count':len(expected),'installed_count':len(installed),'mismatch':mismatch,'extras':extras,'sqlite_numpy_roundtrip':True,'inputs_sha256':{n:hashlib.sha256((target/n).read_bytes()).hexdigest() for n in ['pyproject.toml','requirements.txt','uv.lock']},'installed':installed,'limitation':'PyPI advisory audit and runtime/lock validation only; no full native or container security acceptance'}
(root/'final-runtime-receipt.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps({k:v for k,v in receipt.items() if k!='installed'}),flush=True); assert not mismatch and not extras and 'chromadb' not in installed
