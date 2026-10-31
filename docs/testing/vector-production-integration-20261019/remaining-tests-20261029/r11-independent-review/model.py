from pathlib import Path
import json,hashlib
O=Path('D:/graghRAG-agent/.tmp/r11-independent-review-20261029');p=Path('D:/graghRAG-agent/.tmp/vector-backend-runtime-20261020/model-encode-receipt.json');r=json.loads(p.read_text());m=json.loads((O/'hashmanifest.json').read_text());bad=[]
for n,v in r['files'].items():
 q=Path(r['snapshot'])/n
 with q.open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
 m[str(q)]=d
 if d!=v['sha256']:bad.append(n)
s=json.loads((O/'receipt.json').read_text());s['model_current_hash_mismatch']=bad;s['model_files']=len(r['files']);s['model_revision']=r['revision'];s['git_head']='b1e300f1445c48f9f838bcc0d7b91cb39c1171b2';s['git_branch']='codex/safe-snapshot-20261019';s['r10_inputs_changed_only']=['backend/pyproject.toml','backend/requirements.txt','backend/uv.lock','docs/design/2026-10-19-vector-production-integration.md','docs/plans/2026-10-19-vector-production-integration.md'];(O/'receipt.json').write_text(json.dumps(s,indent=2));(O/'hashmanifest.json').write_text(json.dumps(m,indent=2));print({'model_files':len(r['files']),'mismatch':bad})
