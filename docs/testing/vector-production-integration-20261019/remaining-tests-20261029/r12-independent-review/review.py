from pathlib import Path
import json, hashlib, os, datetime, time, sys
from collections import Counter
import xml.etree.ElementTree as ET
P=Path('D:/graghRAG-agent/.tmp/vector-resume-20261022/full-backend-20261029-r12')
R=Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
O=Path(__file__).parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(n):return json.loads((P/n).read_text())
t=time.monotonic(); out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
for prefix in ('','runtime-'):
 a,b=load(prefix+'before.json'),load(prefix+'after.json')
 bad=[]
 for n,v in b.items():
  f=Path(n) if prefix else R/n
  if not f.is_file() or sha(f)!=v:bad.append(n)
 out[prefix or 'source']={'count':len(b),'pre_post_equal':a==b,'current_hash_differences':bad}
c=load('coverage.json'); files={k.replace('\\','/'):v for k,v in c['files'].items()}; sums=Counter()
sys.path.insert(0,'D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012')
import coverage
os.chdir(R)
cov=coverage.Coverage(config_file=str(R/'docs/testing/coverage-backend-2026-10-12.ini'),data_file=str(P/'backend.coverage'));cov.load()
for n,v in files.items():
 for k in ('covered_lines','num_statements','covered_branches','num_branches','excluded_lines'):sums[k]+=v['summary'][k]
 analysis=cov._analyze(str(R/n))
 assert len(analysis.statements)==v['summary']['num_statements']
 assert len(analysis.statements-analysis.missing)==v['summary']['covered_lines']
 assert set(v['missing_lines'])==analysis.missing
 assert len(set(v['executed_lines']) & analysis.statements)==v['summary']['covered_lines']
 assert len(v['executed_branches'])==v['summary']['covered_branches']
 assert len(v['executed_branches'])+len(v['missing_branches'])==v['summary']['num_branches']
assert all(c['totals'][k]==v for k,v in sums.items())
prod=set()
for base,dirs,names in os.walk(R/'backend'):
 dirs[:]=[d for d in dirs if d not in {'.venv','__pycache__','output','uploads','node_modules','target','tests'}]
 for n in names:
  if n.endswith('.py') and not (Path(base).name=='research' and n.startswith('test_')):prod.add((Path(base)/n).relative_to(R).as_posix())
out['coverage']={'files':len(files),'independent_scope_count':len(prod),'missing':sorted(prod-set(files)),'extra':sorted(set(files)-prod),'raw':dict(sums),'line_percent':100*sums['covered_lines']/sums['num_statements'],'branch_percent':100*sums['covered_branches']/sums['num_branches'],'integer_gate':sums['covered_lines']*100>=sums['num_statements']*90 and sums['covered_branches']*100>=sums['num_branches']*90}
def cases(p):return Counter((x.get('classname'),x.get('name')) for x in ET.parse(p).iter('testcase'))
j=ET.parse(P/'junit.xml'); actual=cases(P/'junit.xml'); old=cases(P.parent/'full-backend-20261029-r11/junit.xml')
def identity(node):
 head,sep,params=node.partition('[');path,_,tail=head.partition('::'); parts=tail.split('::')
 return ('.'.join([path.removeprefix('backend/').removesuffix('.py').replace('/','.'),*parts[:-1]]),parts[-1]+sep+params)
col=Counter(map(identity,load('collected-nodeids.json')))
out['tests']={'count':sum(actual.values()),'baseline':sum(old.values()),'new':sum((actual-old).values()),'missing_baseline':list((old-actual).elements()),'collection_equal':col==actual,'derived_equal':cases(P/'junit-identities-only.xml')==actual,'failure':len(list(j.iter('failure'))),'error':len(list(j.iter('error'))),'skip':len(list(j.iter('skipped'))),'commands':load('commands.json')}
derived=ET.parse(P/'junit-identities-only.xml')
out['safe_junit']={'no_capture_nodes':not any(list(derived.iter(n)) for n in ('system-out','system-err','properties','failure','error')),'sha256':sha(P/'junit-identities-only.xml')}
q=Path('D:/graghRAG-agent/.tmp/vector-backend-runtime-20261020/model-encode-receipt.json'); model=json.loads(q.read_text()); bad=[]
for n,v in model['files'].items():
 f=Path(model['snapshot'])/n
 if f.stat().st_size!=v['bytes'] or sha(f)!=v['sha256']:bad.append(n)
out['model']={'files':len(model['files']),'differences':bad,'receipt_sha256':sha(q)}
out['elapsed_seconds']=time.monotonic()-t
assert out['source']['count']==260 and out['runtime-']['count']==36704
assert all(out[k]['pre_post_equal'] and not out[k]['current_hash_differences'] for k in ('source','runtime-'))
assert len(prod)==len(files)==120 and set(files)==prod and out['coverage']['integer_gate']
assert sum(actual.values())==2223 and sum(old.values())==2201 and not old-actual and actual==col
assert all(x['exit']==0 for x in out['tests']['commands'])
assert not any(out['tests'][k] for k in ('failure','error','skip')) and not bad
out['verdict']='PASS_BACKEND_EVIDENCE_ONLY_NOT_NATIVE_OR_PRODUCTION_ADMISSION'
(O/'receipt.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ('verdict','elapsed_seconds','source','runtime-','coverage','model')},indent=2))
