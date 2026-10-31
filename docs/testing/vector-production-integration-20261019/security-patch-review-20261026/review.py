import base64, concurrent.futures, csv, hashlib, importlib.metadata as md, json, pathlib, re, sys, tomllib, xml.etree.ElementTree as ET
ROOT=pathlib.Path('D:/graghRAG-agent/.tmp/security-lock-patch-20261026')
OUT=pathlib.Path(__file__).parent
OLD=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend')
OLDENV=pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Lib/site-packages')
NEW=ROOT/'.venv/Lib/site-packages'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
norm=lambda s:re.sub(r'[-_.]+','-',s.lower())
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
old=tomllib.loads((OLD/'uv.lock').read_text(encoding='utf-8'))
new=tomllib.loads((ROOT/'backend/uv.lock').read_text(encoding='utf-8'))
oldpk={p['name']:p for p in old['package']};newpk={p['name']:p for p in new['package']}
assert oldpk.keys()==newpk.keys()
diff={n:{'old':oldpk[n]['version'],'new':p['version']} for n,p in newpk.items() if oldpk[n]!=p}
assert set(diff)=={'filelock','opentelemetry-api','setuptools','graphrag-agent-backend'}
for n in set(old)-{'package','manifest'}:assert old[n]==new[n],n
registry={p['name']:p['version'] for p in new['package'] if 'registry' in p.get('source',{})}
installed_list=list(md.distributions());installed={norm(d.metadata['Name']):d.version for d in installed_list}
assert len(installed_list)==len(installed)==159
expected=read(pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/final-runtime-receipt.json'))['installed']
expected.update({'filelock':'4.2.1','opentelemetry-api':'1.45.1','setuptools':'84.1.0'})
assert installed==expected
assert all(registry[n]==v for n,v in installed.items() if n!='langextract')
for key,count in [('pip-audit-all-lock',179),('pip-audit-installed',159)]:
    a=read(ROOT/(key+'.json'))
    scanned={norm(p['name']):p['version'] for p in a['dependencies'] if 'version' in p}
    assert len(scanned)==count,(key,len(scanned))
    assert not any(p.get('vulns') for p in a['dependencies'])
    if key.endswith('all-lock'):assert scanned==registry
    else:assert scanned==installed
    assert not a.get('fixes')
copied=read(ROOT/'copied-unchanged-files.json')
patch_paths=set(); record_counts={}
for d in installed_list:
    name=norm(d.metadata['Name'])
    if name not in {'filelock','opentelemetry-api','setuptools'}:continue
    checked=0
    for f in d.files or []:
        p=d.locate_file(f).resolve()
        if p.is_relative_to(NEW):patch_paths.add(p.relative_to(NEW).as_posix())
        if f.hash:
            assert f.hash.mode=='sha256'
            actual=base64.urlsafe_b64encode(hashlib.sha256(p.read_bytes()).digest()).decode().rstrip('=')
            assert actual==f.hash.value,(name,str(p))
            checked+=1
    record_counts[name]=checked
assert not patch_paths.intersection(copied), sorted(patch_paths.intersection(copied))
def verify(item):
    rel,digest=item
    return [str(base/rel) for base in [OLDENV,NEW] if sha(base/rel)!=digest]
bad=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
    for result in pool.map(verify,copied.items()):bad.extend(result)
assert not bad,bad
j=ET.parse(ROOT/'junit.xml').getroot()
cases=j.findall('.//testcase');assert len(cases)==54
assert not j.findall('.//failure') and not j.findall('.//error') and not j.findall('.//skipped')
receipt=read(ROOT/'runtime-receipt.json')
hashes={n:sha(ROOT/'backend'/n) for n in ['pyproject.toml','requirements.txt','uv.lock']}
assert hashes==receipt['hashes']
reqs={line.strip() for line in (ROOT/'all-lock-requirements.txt').read_text().splitlines() if line.strip()}
assert reqs=={n+'=='+v for n,v in registry.items()}
pths={p.name:p.read_text(errors='replace') for p in NEW.glob('*.pth')}
result={'candidate_sha256':hashes,'lock_changed_packages':diff,'registry_count':len(registry),'installed_count':len(installed),'patch_RECORD_sha256_checked':record_counts,'copied_unchanged_verified_both_sources':len(copied),'patch_paths_copied_overlap':0,'audit_lock_exact_set':179,'audit_installed_exact_set':159,'audit_installed_registry_count':158,'junit_cases':len(cases),'pth':pths,'sys_path':sys.path,'limitations':['No clean full reinstall: initial network and two offline attempts failed; cloned unchanged payload verified','Windows only; no full project coverage or commit approval']}
(OUT/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
