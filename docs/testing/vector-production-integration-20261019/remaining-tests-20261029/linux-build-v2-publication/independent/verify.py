import ast,hashlib,json,pathlib
O=pathlib.Path(__file__).resolve().parent
D=O.parents[2]; A=D/'linux-build-isolated-candidate-20261029-v2'; V=D/'linux-build-isolated-candidate-20261029'
C=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((A/'evidence-manifest.json').read_text()); assert len(manifest)==52
assert all(sha(A/p)==h for p,h in manifest.items())
baseline=json.loads((D/'vector-resume-20261022/full-backend-20261029-r11/before.json').read_text()); assert len(baseline)==258
assert all(sha(C/p)==h for p,h in baseline.items())
old=D/'linux-vector-bridge-20261028'; vend=json.loads((old/'vendor-integrity.json').read_text()); count=0
for name,package in vend['packages'].items():
 for f,h in package['files'].items(): assert sha(old/'vendor'/name/f)==h; count+=1
assert count==447
b=A/'backend/native/vector_numeric/build.py'; assert sha(b)=='27242d74c351a6d25ed2163d626e7afd3728692df30dfd739a6c2a9c5b8e5082'
new=ast.parse(b.read_text()); prior=ast.parse((V/'backend/native/vector_numeric/build.py').read_text())
# Installer is identical, and only documentation and five command prefix changes exist in build source.
get=lambda tree,name:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
assert ast.dump(get(new,'install'))==ast.dump(get(prior,'install'))
launches=[n.args[0].elts for n in ast.walk(get(new,'build')) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run']
assert len(launches)==5
for elts in launches:
 vals=[e.value if isinstance(e,ast.Constant) else None for e in elts]
 assert vals[:3]==['rustup','run','1.94.0'] and vals[3] in ('rustc','cargo') and '--install' not in vals
 if vals[3]=='cargo' and vals[4]!='--version': assert '--offline' in vals and '--locked' in vals
receipt=json.loads((A/'real-build-r2/build-receipt.json').read_text()); ev=json.loads((A/'real-build-r2/build-evidence.json').read_text())
assert receipt['approved'] is False and ev['build_script_sha256']==sha(b)
for p in ('Cargo.toml','Cargo.lock','rust-toolchain.toml','src/main.rs'):
 assert sha(A/'backend/native/vector_numeric'/p)==sha(C/'backend/native/vector_numeric'/p)==receipt['files'][p]==sha(V/'backend/native/vector_numeric'/p)
assert sha(A/'real-build-r2/vector-numeric-bridge')==receipt['files']['vector-numeric-bridge']=='20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0'
assert all(c['exit_code']==0 for c in ev['commands']) and len(ev['commands'])==5
assert ev['compiled']=={'serde_json':['std'],'serde_core':['std'],'zmij':[]}
assert json.loads((A/'real-build-r2/source-stability.json').read_text())['equal'] is True
neg=json.loads((A/'real-build-r2/missing-toolchain.json').read_text()); assert neg['exit_code']==1 and 'is not installed' in neg['stderr'] and neg['files_after']==['settings.toml']
ins=json.loads((A/'real-build-r2/inspect.json').read_text())[0]; host=ins['HostConfig']
assert host['NetworkMode']=='none' and host['ReadonlyRootfs'] and ins['Config']['User']=='1000:1000'
assert all(not m['RW'] for m in ins['Mounts'] if m['Destination'] in ('/input','/runner.py','/config','/vendor'))
binding=json.loads((A/'binding-receipt.json').read_text())
assert sha(old/'vendor-integrity.json')==binding['vendor_manifest_sha256'] and sha(old/'cargo-home/config.toml')==binding['cargo_config_sha256']
(O/'result.json').write_text(json.dumps(dict(manifest_files=52,C_R11_inputs=258,vendor_files=count,command_prefixes=5,installer_ast_unchanged=True,script_sha256=sha(b),real_build_evidence_valid=True,missing_toolchain_evidence_valid=True),indent=2))
print((O/'result.json').read_text())
