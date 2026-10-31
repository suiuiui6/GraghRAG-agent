import pathlib,json,hashlib,tomllib,base64,tarfile
O=pathlib.Path(__file__).resolve().parent; D=O.parent
A=D/'chroma-build-provenance-20261026'; B=D/'chroma-build-provenance-20261027'
inventory={}
def read(p):
 b=p.read_bytes();inventory[str(p)]=hashlib.sha256(b).hexdigest();return b
def js(p):return json.loads(read(p).decode('utf-8-sig'))
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
tree=js(A/'github-tree.json');assert tree['truncated'] is False
tree={x['path']:x['sha'] for x in tree['tree']}
lockraw=read(B/'original-Cargo.lock');assert blob(lockraw)==tree['Cargo.lock']
lock=tomllib.loads(lockraw.decode());special=('float_roundtrip','arbitrary_precision','unbounded_depth')
sj=[x for x in lock['package'] if x['name']=='serde_json'];assert len(sj)==1 and sj[0]['version']=='1.0.149'
manifests={}
for p in tree:
 if p.endswith('Cargo.toml'):
  b=read(B/'original-workspace'/p.replace('/','__'));assert blob(b)==tree[p]
  assert not any(s in b.decode() for s in special)
  manifests[p]=tomllib.loads(b.decode())
assert len(manifests)==37
consumers=[p for p in lock['package'] if any(x.split()[0]=='serde_json' for x in p.get('dependencies',[]))];assert len(consumers)==51
records=[]
for p in consumers:
 if p.get('source','').startswith('registry+'):
  j=js(B/'index'/(p['name']+'.json'));b=base64.b64decode(j['content']);assert blob(b)==j['sha']
  e=[json.loads(l) for l in b.splitlines() if l and json.loads(l)['vers']==p['version']];assert len(e)==1
  e=e[0];assert e['cksum']==p['checksum'] and not any(s in json.dumps(e) for s in special)
  # Inspect ALL target/kind/optional records, never filter for Windows.
  deps=[x for x in e['deps'] if x['name']=='serde_json' or x.get('package')=='serde_json'];assert deps
  records.append(dict(name=p['name'],version=p['version'],dependencies=deps))
assert len(records)==30
local=[p for p in consumers if not p.get('source')];assert len(local)==20
assert all(any(m.get('package',{}).get('name')==p['name'] for m in manifests.values()) for p in local)
git=[p for p in consumers if p.get('source','').startswith('git+')];assert len(git)==1 and git[0]['source'].endswith('#bd8ec9581e00034363befe7d38146084df018876')
gt=js(B/'gcloud-tree.json');assert gt['truncated'] is False;gt={x['path']:x['sha'] for x in gt['tree']}
for orig,file in [('Cargo.toml','gcloud-root.Cargo.toml'),('foundation/auth/Cargo.toml','gcloud-auth.Cargo.toml')]:
 b=read(B/file);assert blob(b)==gt[orig] and not any(s in b.decode() for s in special)
crate=D/'vector-formatter-20261020/upstream/serde_json-1.0.149.crate';assert hashlib.sha256(read(crate)).hexdigest()==sj[0]['checksum']
with tarfile.open(crate) as tf: cm=tomllib.loads(tf.extractfile('serde_json-1.0.149/Cargo.toml').read().decode())
assert cm['features']['default']==['std']
for f in ('alloc','std','preserve_order','raw_value'):assert not any(s in json.dumps(cm['features'][f]) for s in special)
wf=read(A/'.github__workflows___build_release_pypi.yml');assert blob(wf)==tree['.github/workflows/_build_release_pypi.yml']
py=read(A/'pyproject.toml');assert blob(py)==tree['pyproject.toml'];assert tomllib.loads(py.decode())['tool']['maturin']['features']==['pyo3/extension-module']
act=read(B/'rust-action.yaml');assert blob(act)==tree['.github/actions/rust/action.yaml']
assert not any(x.startswith('.cargo/config') for x in tree)
bun=js(O/'linux-bundle.json'); statement=json.loads(base64.b64decode(bun['dsseEnvelope']['payload']))
(O/'decoded-statement-UNVERIFIED.json').write_text(json.dumps(statement,indent=2),encoding='utf-8')
result=dict(status='source-declared-platform-conservative-feature-superset-passed',manifest_count=37,consumer_count=51,registry_count=30,local_count=20,git_count=1,registry_all_target_dependencies=records,inputs_sha256=inventory,linux_delta='Linux x86_64 and --zig selected by fixed release matrix; no new serde_json feature requested; all target/kind dependency records already included',attestation_signature_verified=False)
(O/'source-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['status'],37,51)
