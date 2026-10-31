from pathlib import Path
import json,hashlib,xml.etree.ElementTree as E,collections,os,time,email,re
O=Path('D:/graghRAG-agent/.tmp/r11-independent-review-20261029'); R=Path('D:/graghRAG-agent/.tmp/vector-resume-20261022/full-backend-20261029-r11'); C=Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent'); V=Path('D:/graghRAG-agent/.tmp/backend-runtime-20261029'); A=Path('D:/graghRAG-agent/.tmp/installed-windows-audit-20261029')
def j(p):return json.loads(p.read_text())
def h(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
receipt={}; manifest={}
for name in ['before.json','after.json','runtime-before.json','runtime-after.json','coverage.json','junit.xml','collected-nodeids.json','collect.log','commands.json','tests.log','export.log','backend.coverage']:
 manifest[str(R/name)]=h(R/name)
b=j(R/'before.json');a=j(R/'after.json');rb=j(R/'runtime-before.json');ra=j(R/'runtime-after.json')
receipt['source_before_after_equal']=b==a; receipt['runtime_before_after_equal']=rb==ra
receipt['source_count']=len(b); receipt['source_current_mismatch']=[k for k,v in b.items() if h(C/k)!=v]
manifest.update({str(C/k):h(C/k) for k in b})
cov=j(R/'coverage.json'); files=cov['files']; totals={k:sum(x['summary'][k] for x in files.values()) for k in ['covered_lines','num_statements','covered_branches','num_branches']}
receipt['recomputed_totals']=totals;receipt['totals_equal_report']=all(cov['totals'][k]==v for k,v in totals.items()); receipt['line_gate']=totals['covered_lines']*100>=totals['num_statements']*90; receipt['branch_gate']=totals['covered_branches']*100>=totals['num_branches']*90
prod=set()
for base,dirs,names in os.walk(C/'backend'):
 dirs[:]=[x for x in dirs if x not in {'.venv','__pycache__','output','uploads','node_modules','target','tests'}]
 for n in names:
  if n.endswith('.py') and not ('research' in Path(base).parts and n.startswith('test_')):prod.add((Path(base)/n).relative_to(C).as_posix())
measured={k.replace('\\','/') for k in files};receipt['production_count']=len(prod);receipt['missing_production']=sorted(prod-measured);receipt['extra_production']=sorted(measured-prod);receipt['zero_covered_files']=[k for k,v in files.items() if v['summary']['covered_lines']==0]
def ident(x):return x.get('classname'),x.get('name')
root=E.parse(R/'junit.xml').getroot(); cases=list(root.iter('testcase'));observed=collections.Counter(ident(x) for x in cases);old=collections.Counter(ident(x) for x in E.parse(R.parent/'full-backend-20261028-r10/junit.xml').getroot().iter('testcase'))
receipt['junit_counts']={'cases':len(cases),**{n:len(list(root.iter(n))) for n in ['failure','error','skipped']}};receipt['baseline_count']=sum(old.values());receipt['missing_baseline']=list((old-observed).elements());receipt['extra_baseline']=list((observed-old).elements())
nodes=j(R/'collected-nodeids.json'); raw=[x.strip() for x in (R/'collect.log').read_text(encoding='utf8',errors='replace').splitlines() if x.startswith(('backend/tests/','backend/research/','tests/','research/')) and '::' in x];receipt['collection_raw_equal']=nodes==raw
def ni(n):
 head,br,params=n.partition('[');path,_,tail=head.partition('::');parts=tail.split('::');return '.'.join([path.removeprefix('backend/').removesuffix('.py').replace('/','.'),*parts[:-1]]),parts[-1]+br+params
receipt['collection_counter_equal']=collections.Counter(map(ni,nodes))==observed;receipt['collection_unique']=len(nodes)==len(set(nodes));receipt['commands']=j(R/'commands.json')
receipt['real_case_identities']=[{'classname':x.get('classname'),'name':x.get('name'),'time':x.get('time')} for x in cases if any(t in (x.get('classname','')+' '+x.get('name','')) for t in ['vector_http_lifecycle','real_model'])]
# Independently enumerate runtime scope and hash every recorded file.
base=Path('D:/graghRAG-agent/.tmp/python-security-runtime-20261028/derived/python');tool=Path('D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012');driver=R.parent/'run_backend_20261029_r11.py'
expected={str(p) for p in base.rglob('*') if p.is_file()};expected.add(str(driver.resolve()))
expected|={str(p) for p in tool.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for top in [V/'.venv',V/'backend']:expected|={str(p) for p in top.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
expected|={str(V/n) for n in ['receipt.json','copied-unchanged-files.json','copy-post-verification.json','config-binding.json','wheel-verification.json','installed-wheel-records.json','installed-pre.json','installed-post.json','package-set.json','verified-wheels.txt','hashes.json','local-source-metadata.json']}
receipt['runtime_count']=len(rb);receipt['runtime_enumeration_missing']=sorted(expected-set(rb));receipt['runtime_enumeration_extra']=sorted(set(rb)-expected)
(O/'progress.json').write_text(json.dumps(receipt,indent=2)); mismatch=[];start=time.time()
for i,(k,v) in enumerate(rb.items()):
 actual=h(Path(k));manifest[k]=actual
 if actual!=v:mismatch.append(k)
 if i%1000==0:(O/'hash-progress.json').write_text(json.dumps({'done':i,'total':len(rb),'seconds':time.time()-start}))
receipt['runtime_current_mismatch']=mismatch;receipt['runtime_hash_seconds']=time.time()-start
meta=[]
for p in (V/'.venv/Lib/site-packages').glob('*.dist-info/METADATA'):
 msg=email.message_from_bytes(p.read_bytes());meta.append({'name':re.sub('[-_.]+','-',msg['Name'].lower()),'version':msg['Version'],'metadata_sha256':h(p)})
receipt['metadata_count']=len(meta); recorded=j(A/'installed-metadata.json');receipt['metadata_equal']=sorted(meta,key=lambda x:x['name'])==sorted(recorded,key=lambda x:x['name']);receipt['patched_versions']={x['name']:x['version'] for x in meta if x['name'] in ['langgraph','langgraph-sdk','msgpack']}
audit=j(A/'audit.json'); deps=audit['dependencies'];actualpairs={(x['name'],x['version']) for x in meta if x['name']!='langextract'};auditpairs={(re.sub('[-_.]+','-',x['name'].lower()),x['version']) for x in deps};receipt['audit_pairs_equal']=actualpairs==auditpairs;receipt['audit_count']=len(deps);receipt['audit_vulnerabilities']=sum(len(x.get('vulns',[])) for x in deps);receipt['audit_skips']=[x['name'] for x in deps if 'skip_reason' in x];receipt['attempt0_preserved']=(A/'attempt0-network-denied').is_dir()
for p in A.rglob('*'):
 if p.is_file():manifest[str(p)]=h(p)
receipt['finished_utc']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
(O/'receipt.json').write_text(json.dumps(receipt,indent=2));(O/'hashmanifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k not in ['commands','real_case_identities']},indent=2))


