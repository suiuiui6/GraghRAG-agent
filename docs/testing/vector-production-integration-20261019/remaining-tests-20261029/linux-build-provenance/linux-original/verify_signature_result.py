import pathlib,json,hashlib
O=pathlib.Path(__file__).resolve().parent
command=json.loads((O/'gh-command.json').read_text(encoding='utf-8'));assert command['exit']==0
v=json.loads((O/'gh-verification.json').read_text(encoding='utf-8'))
assert len(v)==1;v=v[0]['verificationResult']; c=v['signature']['certificate']
identity='https://github.com/chroma-core/chroma/.github/workflows/_build_release_pypi.yml@refs/tags/1.5.9'
assert c['issuer']=='https://token.actions.githubusercontent.com'
assert c['subjectAlternativeName']==identity
assert c['sourceRepositoryDigest']=='11f3c7435e71024aa0a2b53710a28d3289d922d1'
assert c['sourceRepositoryRef']=='refs/tags/1.5.9'
assert c['sourceRepositoryURI']=='https://github.com/chroma-core/chroma'
j=json.loads((O/'selection.json').read_text(encoding='utf-8'));p=O/j['filename']
assert p.stat().st_size==j['size']
h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==j['digests']['sha256']
s=v['statement']['subject'];assert len(s)==1 and s[0]['name']==j['filename'] and s[0]['digest']['sha256']==h
assert v['verifiedTimestamps']
source=json.loads((O/'source-verification.json').read_text(encoding='utf-8'));assert source['manifest_count']==37 and source['consumer_count']==51
result=dict(status='linux-original-artifact-signature-and-declared-source-feature-premise-verified',wheel_sha256=h,wheel_bytes=p.stat().st_size,certificate=c,verified_timestamps=v['verifiedTimestamps'],source_verification_sha256=hashlib.sha256((O/'source-verification.json').read_bytes()).hexdigest(),production_gate_approved=False,limitations='same usual upstream source/lock/config execution premise as existing Windows contract; not actual rustc trace or native security clearance')
(O/'final-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['status'])
