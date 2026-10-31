"""Independent read-only source/build evidence audit; outputs only to this directory."""
import base64, datetime, hashlib, json, pathlib, tarfile, tomllib
OUT = pathlib.Path(__file__).resolve().parent
D = OUT.parent.parent
B = D/'.tmp/chroma-build-provenance-20261027'
A = D/'.tmp/chroma-build-provenance-20261026'
C = pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
inventory = {}
def data(p):
    b = p.read_bytes(); inventory[str(p)] = hashlib.sha256(b).hexdigest(); return b
def js(p): return json.loads(data(p).decode('utf-8-sig'))
def blob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
tree_doc = js(A/'github-tree.json'); assert tree_doc.get('truncated') is False
tree = {e['path']:e['sha'] for e in tree_doc['tree']}
assert not any(p.startswith('.cargo/config') for p in tree)
special = ('float_roundtrip','arbitrary_precision','unbounded_depth')
lock_b = data(B/'original-Cargo.lock'); assert blob(lock_b)==tree['Cargo.lock']
lock = tomllib.loads(lock_b.decode())
sj = [p for p in lock['package'] if p['name']=='serde_json']; assert len(sj)==1
assert sj[0]['version']=='1.0.149'
consumers = [p for p in lock['package'] if any(d.split()[0]=='serde_json' for d in p.get('dependencies',[]))]
assert len(consumers)==51
manifests = {}
for path in tree:
    if path.endswith('Cargo.toml'):
        raw=data(B/'original-workspace'/path.replace('/','__'))
        assert blob(raw)==tree[path], path
        assert not any(f in raw.decode() for f in special),path
        manifests[path]=tomllib.loads(raw.decode())
assert len(manifests)==37
local = [p for p in consumers if not p.get('source')]
assert len(local)==20
for p in local:
    assert any(m.get('package',{}).get('name')==p['name'] for m in manifests.values())
registry = [p for p in consumers if p.get('source','').startswith('registry+')]
assert len(registry)==30
index_records=[]
for p in registry:
    obj=js(B/'index'/(p['name']+'.json')); raw=base64.b64decode(obj['content'])
    assert blob(raw)==obj['sha']
    entries=[json.loads(line) for line in raw.splitlines() if line]
    exact=[e for e in entries if e['vers']==p['version']]; assert len(exact)==1
    e=exact[0]; assert e['cksum']==p['checksum']
    assert not any(f in json.dumps(e) for f in special),p['name']
    dep=[d for d in e['deps'] if d['name']=='serde_json' or d.get('package')=='serde_json']
    assert dep,p['name']
    index_records.append({'name':p['name'],'version':p['version'],'checksum':e['cksum'],'features':e['features'],'features2':e.get('features2',{}),'serde_dependencies':dep})
git=[p for p in consumers if p.get('source','').startswith('git+')]
assert len(git)==1 and git[0]['name']=='gcloud-auth'
assert git[0]['source'].endswith('#bd8ec9581e00034363befe7d38146084df018876')
gt=js(B/'gcloud-tree.json'); assert gt.get('truncated') is False
gmap={e['path']:e['sha'] for e in gt['tree']}
for original,local_file in [('Cargo.toml','gcloud-root.Cargo.toml'),('foundation/auth/Cargo.toml','gcloud-auth.Cargo.toml')]:
    raw=data(B/local_file); assert blob(raw)==gmap[original]
    assert not any(f in raw.decode() for f in special)
assert tomllib.loads(data(B/'gcloud-auth.Cargo.toml').decode())['dependencies']['serde_json']=={'version':'1.0'}
crate=D/'.tmp/vector-formatter-20261020/upstream/serde_json-1.0.149.crate'
assert hashlib.sha256(data(crate)).hexdigest()==sj[0]['checksum']
with tarfile.open(crate) as tf:
    cm=tomllib.loads(tf.extractfile('serde_json-1.0.149/Cargo.toml').read().decode())
assert cm['features']['default']==['std']
for f in ('alloc','std','preserve_order','raw_value'):
    assert not any(s in json.dumps(cm['features'][f]) for s in special)
for path,filename in [('.github/workflows/_build_release_pypi.yml','.github__workflows___build_release_pypi.yml'),('pyproject.toml','pyproject.toml'),('Cargo.toml','Cargo.toml')]:
    assert blob(data(A/filename))==tree[path]
assert blob(data(B/'rust-action.yaml'))==tree['.github/actions/rust/action.yaml']
py=tomllib.loads(data(A/'pyproject.toml').decode())
assert py['tool']['maturin']['features']==['pyo3/extension-module']
v=js(OUT/'gh-verify-network.json')[0]['verificationResult']
cert=v['signature']['certificate']
assert cert['sourceRepositoryDigest']=='11f3c7435e71024aa0a2b53710a28d3289d922d1'
assert cert['sourceRepositoryRef']=='refs/tags/1.5.9'
assert cert['issuer']=='https://token.actions.githubusercontent.com'
assert cert['subjectAlternativeName']=='https://github.com/chroma-core/chroma/.github/workflows/_build_release_pypi.yml@refs/tags/1.5.9'
wheel=A/'chromadb-1.5.9-cp39-abi3-win_amd64.whl'
wh=hashlib.sha256(data(wheel)).hexdigest()
assert wh=='4fd0b560e56761b7f3cb4d5c6205fd5f20814484b4a3e4e9af9038c2b428fc6c'
assert v['statement']['subject'][0]['digest']['sha256']==wh and v['verifiedTimestamps']
release=js(A/'pypi-release.json')
assert next(e for e in release['urls'] if e['filename']==wheel.name)['digests']['sha256']==wh
prior=js(D/'.tmp/formatter-admission-review-20261026/verification.json')
unchanged=[]; changed=[]
for path,expected in prior['inputs_sha256'].items():
    actual=hashlib.sha256(data(pathlib.Path(path))).hexdigest()
    (unchanged if actual==expected else changed).append(path)
assert not changed,changed
data(D/'.tmp/formatter-admission-review-20261026/REVIEW.md')
data(B/'REPORT.md'); data(B/'verify_evidence.py'); data(B/'evidence-verification.json')
data(B/'gh-verification-network.json'); data(B/'bundle.json')
data(OUT/'gh-verify.stderr'); data(OUT/'gh-verify-network.stderr')
data(OUT/'verify.py')
assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in inventory.items())
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':0,'scope':'static source/build evidence; no Chroma import/execution; no C writes','wheel_sha256':wh,'source_commit':cert['sourceRepositoryDigest'],'manifests':len(manifests),'consumers':len(consumers),'registry':len(registry),'local':len(local),'git':len(git),'index_records':index_records,'prior_algorithm_review_inputs_unchanged':len(unchanged),'inputs_sha256':inventory,'interpretation':'Declared feature superset excludes three special features. Actual build settings are inferred under trust in signed official source/workflow; they are not cryptographically enumerated.'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('index_records','inputs_sha256')},indent=2))
