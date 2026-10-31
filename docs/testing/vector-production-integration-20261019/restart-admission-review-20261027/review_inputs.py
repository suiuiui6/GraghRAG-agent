import hashlib, json, difflib
from pathlib import Path
C=Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
D=Path('D:/graghRAG-agent/.tmp')
out=D/'restart-admission-review-20261027'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((D/'vector-resume-20261022/full-backend-20261026-r4/before.json').read_text(encoding='utf-8-sig'))
candidate=D/'model-restart-fix-20261027/test_vector_http_lifecycle.py'
current=C/'backend/tests/test_vector_http_lifecycle.py'
s=current.read_text(encoding='utf-8')
assert current.read_bytes()==candidate.read_bytes()
old=s.replace('args = json.load(sys.stdin)', 'args = json.loads(sys.argv[1])').replace("[sys.executable, '-c', program], input=json.dumps(", "[sys.executable, '-c', program, json.dumps(").replace("'profile': service.model_profile}),", "'profile': service.model_profile})],")
target=baseline['backend/tests/test_vector_http_lifecycle.py']
variants={e:hashlib.sha256(old.replace('\n',e).encode()).hexdigest() for e in ['\n','\r\n']}
assert target in variants.values(), (target, variants)
(out/'lifecycle-reviewed.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), s.splitlines(True), fromfile='R4-bound-baseline',tofile='stdin-candidate')),encoding='utf-8')
record={'baseline_manifest_sha256':sha(D/'vector-resume-20261022/full-backend-20261026-r4/before.json'),'lifecycle_baseline_sha256':target,'reverse_transport_only_reconstructs_baseline':True,'candidate_matches_C':True,'hashes':{}}
files=[candidate,current,D/'model-admission-tests-20261027/test_vector_model_admission_failures.py',D/'model-restart-debug-20261027/test_restart_credential_transport.py',C/'backend/tests/test_vector_backup_rejection_contracts.py',C/'backend/tests/test_vector_publication_backup.py']
manifest=json.loads((D/'model-admission-tests-20261027/inputs-before.json').read_text())
for p in files:record['hashes'][str(p)]=sha(p)
record['admission_input_drift']=[k for k,v in manifest.items() if sha(C/k if k.startswith('backend/') else D/'model-admission-tests-20261027'/k)!=v]
assert not record['admission_input_drift']
b=C/'backend/tests/test_vector_backup_rejection_contracts.py'
bs=b.read_text(encoding='utf-8')
assert 'from backend.tests.test_vector_publication_backup import' in bs
previous=bs.replace('from backend.tests.test_vector_publication_backup import','from test_vector_publication_backup import')
r3=json.loads((D/'vector-resume-20261022/full-backend-20261026-r3/before.json').read_text(encoding='utf-8-sig'))
record['backup_reverse_import_only_matches_R3']=r3['backend/tests/test_vector_backup_rejection_contracts.py'] in [hashlib.sha256(previous.replace('\n',e).encode()).hexdigest() for e in ['\n','\r\n']]
assert record['backup_reverse_import_only_matches_R3']
(out/'inputs-reviewed.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
