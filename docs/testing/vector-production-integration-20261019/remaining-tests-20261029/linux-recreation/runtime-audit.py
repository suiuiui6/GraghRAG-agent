import json,hashlib,os,re,importlib.metadata as md,subprocess,sys
from pathlib import Path
norm=lambda s:re.sub(r'[-_.]+','-',s).lower()
expected=json.loads(Path('/opt/graphrag-artifacts/expected-packages.json').read_text())
rows=[(norm(d.metadata['Name']),d.version) for d in md.distributions()]
assert len(rows)==len(dict(rows))==158
assert dict(rows)==expected
p=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True,timeout=40);assert p.returncode==0,p.stdout+p.stderr
paths=['/source','/source/backend','/source/backend/native','/source/backend/native/vector_numeric','/source/backend/native/vector_numeric/bin','/source/backend/native/vector_numeric/bin/x86_64-unknown-linux-gnu','/source/backend/native/vector_numeric/bin/x86_64-unknown-linux-gnu/vector-numeric-bridge','/models','/models/bge-small-zh-v1.5','/models/bge-small-zh-v1.5/model.safetensors','/opt','/opt/graphrag-cpu','/opt/graphrag-cpu/venv','/opt/graphrag-cpu/venv/lib/python3.12/site-packages']
permissions={s:{'uid':Path(s).stat().st_uid,'mode':oct(Path(s).stat().st_mode & 0o777),'writable':os.access(s,os.W_OK)} for s in paths}
assert not any(v['writable'] for v in permissions.values()),permissions
Path('/evidence/runtime-identity.json').write_text(json.dumps({'packages':dict(rows),'count':len(rows),'pip_check':p.stdout,'pip_check_exit':p.returncode,'permissions':permissions},indent=2))
print('158 unique exact versions; pip check; all inspected parent paths nonwritable PASS')
