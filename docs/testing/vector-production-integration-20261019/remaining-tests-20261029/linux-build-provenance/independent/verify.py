import pathlib,json,hashlib,subprocess,sys
O=pathlib.Path(__file__).resolve().parent; D=O.parent
A=D/'linux-build-isolated-candidate-20261029'; B=D/'linux-chroma-provenance-gap-20261029'
C=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={}
baseline=json.loads((D/'vector-resume-20261022/full-backend-20261029-r11/before.json').read_text())
assert all(sha(C/p)==h for p,h in baseline.items());result['C_R11_unchanged']=len(baseline)
receipt=json.loads((A/'real-build-r1/build-receipt.json').read_text())
assert receipt['approved'] is False
h=sha(A/'real-build-r1/vector-numeric-bridge');assert h==receipt['files']['vector-numeric-bridge']=='20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0'
for p in ('Cargo.toml','Cargo.lock','rust-toolchain.toml','src/main.rs'):
 assert sha(A/'backend/native/vector_numeric'/p)==sha(C/'backend/native/vector_numeric'/p)==receipt['files'][p]
result['binary_sha256']=h
old=D/'linux-vector-bridge-20261028'; vend=json.loads((old/'vendor-integrity.json').read_text());count=0
for name,package in vend['packages'].items():
 for f,h in package['files'].items():assert sha(old/'vendor'/name/f)==h;count+=1
result['vendor_files_verified']=count
ev=json.loads((A/'real-build-r1/build-evidence.json').read_text())
assert ev['compiled']=={'serde_json':['std'],'serde_core':['std'],'zmij':[]}
assert all(c['exit_code']==0 for c in ev['commands'])
assert receipt['features']==['serde_json/std','zmij/default']
assert len(json.dumps({**receipt,'approved':True},indent=2).encode())<=8192
result['real_command_count']=len(ev['commands'])
# Replay source audit with exact original input paths, redirect all outputs to owned directory.
source=(B/'verify_source.py').read_text()
source=source.replace("O=pathlib.Path(__file__).resolve().parent; D=O.parent",f"O=pathlib.Path({str(B)!r}); D=O.parent")
source=source.replace("(O/'decoded-statement-UNVERIFIED.json').write_text", "(pathlib.Path(__file__).parent/'decoded-statement-UNVERIFIED.json').write_text")
source=source.replace("(O/'source-verification.json').write_text", "(pathlib.Path(__file__).parent/'source-verification.json').write_text")
exec(compile(source,str(O/'source-audit-replay.py'),'exec'),{'__file__':str(O/'source-audit-replay.py')})
cmd=json.loads((B/'gh-command.json').read_text())['command']
run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=55)
(O/'gh-verification.json').write_text(run.stdout,encoding='utf-8');(O/'gh-verification.stderr').write_text(run.stderr,encoding='utf-8')
result['gh_exit']=run.returncode
(O/'result.json').write_text(json.dumps(result,indent=2))
assert run.returncode==0,run.stderr
v=json.loads(run.stdout)[0]['verificationResult'];c=v['signature']['certificate']
assert c['issuer']=='https://token.actions.githubusercontent.com'
assert c['subjectAlternativeName']=='https://github.com/chroma-core/chroma/.github/workflows/_build_release_pypi.yml@refs/tags/1.5.9'
assert c['sourceRepositoryDigest']=='11f3c7435e71024aa0a2b53710a28d3289d922d1'
assert c['sourceRepositoryRef']=='refs/tags/1.5.9'
wheel=B/'chromadb-1.5.9-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
assert wheel.stat().st_size==23316203
assert sha(wheel)=='cc09b3df76e5a5cb386aed2715a2eea152e3949f9e1ba93c7119505377749929'
assert v['statement']['subject']==[{'name':wheel.name,'digest':{'sha256':sha(wheel)}}]
assert v['verifiedTimestamps']
result['independent_signature_and_source_verified']=True
(O/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
