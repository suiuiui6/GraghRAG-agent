import pathlib,tomllib,json,hashlib,collections,html.parser,urllib.parse
from pip._vendor.packaging.markers import Marker
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name
p=pathlib.Path(__file__).parent;a=p.parent/'linux-cpu-direct-url-20261028';old=p.parent/'linux-backend-cpu-candidate-20261028';c=pathlib.Path(r'C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent');sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();read=lambda f:tomllib.loads(f.read_text(encoding='utf-8-sig'))
before=json.loads((a/'inputs-before.json').read_text());assert all(sha(c/name)==sha(a/'baseline'/name)==h for name,h in before['C'].items())
project=read(a/'candidate/backend/pyproject.toml');base=read(a/'baseline/backend/uv.lock');lock=read(a/'candidate/backend/uv.lock');assert sha(a/'candidate/backend/uv.lock')=='d1434b9b8b46f3d9c061098e15ddaada44e8d0a2d3dfb55d4db4c425a8f60b36'
b={v['name']:v for v in base['package']};d={v['name']:v for v in lock['package']};assert len(b)==len(base['package']) and len(d)==len(lock['package'])==159
assert project['project']['requires-python']==lock['requires-python']=='==3.12.*';assert project['tool']['uv']['environments']==["sys_platform == 'linux' and platform_machine == 'x86_64'"]
url='https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl';digest='a09987c95ec4cffdb6df798d3d641558110a334cfccce22f2f046d83142bc260';torch=d['torch'];assert torch['version']=='2.14.0+cpu' and torch['source']=={'url':url} and torch['wheels']==[{'url':url,'hash':'sha256:'+digest}]
assert any(Requirement(v).url==url+'#sha256='+digest for v in project['project']['dependencies'] if Requirement(v).name=='torch')
index=(old/'torch-cpu-index.html').read_text();assert sha(old/'torch-cpu-index.html')=='afbb7e04f36d5c3d8b7141bcf10682954f05bb4d5f0297876127ffbb93f015f8';assert url+'#sha256='+digest in index
for name,pkg in d.items():
 if name=='torch':continue
 assert pkg['version']==b[name]['version'] and pkg['source']==b[name]['source'],name
 getart=lambda x:{(f['url'],f['hash']) for f in x.get('wheels',[])+([x['sdist']] if 'sdist' in x else [])}
 assert getart(pkg)<=getart(b[name]),name
rootdeps=project['project']['dependencies'];dev=project['dependency-groups']['dev']
def walk(pkgs,micro,allgroups):
 env={'implementation_name':'cpython','implementation_version':f'3.12.{micro}','os_name':'posix','platform_machine':'x86_64','platform_python_implementation':'CPython','platform_release':'','platform_system':'Linux','platform_version':'','python_full_version':f'3.12.{micro}','python_version':'3.12','sys_platform':'linux','extra':''}
 active=lambda marker,extras: not marker or any(Marker(marker).evaluate({**env,'extra':e}) for e in ['']+list(extras))
 queue=collections.deque();seen={};edges=set()
 for text in rootdeps+(dev if allgroups else []):
  req=Requirement(text)
  if active(str(req.marker) if req.marker else None,[]):queue.append((canonicalize_name(req.name),set(req.extras)))
 while queue:
  name,extras=queue.popleft();assert name in pkgs
  if name in seen and extras<=seen[name]:continue
  seen.setdefault(name,set()).update(extras);pkg=pkgs[name];deps=list(pkg.get('dependencies',[]))
  for extra in seen[name]:deps+=pkg.get('optional-dependencies',{}).get(extra,[])
  for dep in deps:
   if active(dep.get('marker'),seen[name]):
    ex=set(dep.get('extra',[]));queue.append((dep['name'],ex));edges.add((name,dep['name'],tuple(sorted(ex))))
 return seen,edges
report={'status':'read-only independent lock/graph review; not installed inventory','input_sha256':{str(f.relative_to(a)):sha(f) for f in [a/'candidate/backend/uv.lock',a/'candidate/backend/pyproject.toml',a/'actual-graph-diff.json',a/'root-lock-check-online-20261029.result.json']},'main_inputs_unchanged':before['C'],'all_lock_count':159,'all_removed':sorted(set(b)-set(d)),'all_added':sorted(set(d)-set(b)),'torch':torch,'scopes':{}}
author=json.loads((a/'actual-graph-diff.json').read_text())
for title,allgroups,count in [('runtime',False,133),('all_groups',True,158)]:
 ns,edges=walk(d,16,allgroups);bs,_=walk(b,16,allgroups);assert len(ns)==count
 assert set(ns)=={x['name'] for x in author['scopes'][title]['packages']};assert edges=={(x['parent'],x['child'],tuple(sorted(x.get('requested_extras',[])))) for x in author['scopes'][title]['edges']}
 assert not any(n.startswith(('nvidia-','cuda-')) or n=='triton' for n in ns);assert set(ns)-set(bs)==set()
 changes=[n for n in ns if b[n]['version']!=d[n]['version']];assert changes==['torch']
 for micro in [0,8,16,20]:assert set(walk(d,micro,allgroups)[0])==set(ns)
 report['scopes'][title]={'count':len(ns),'registry_count':sum('registry' in d[n]['source'] for n in ns),'url_count':sum('url' in d[n]['source'] for n in ns),'editable_count':sum('editable' in d[n]['source'] for n in ns),'names':sorted(ns),'removed':sorted(set(bs)-set(ns)),'version_changes':[{'name':n,'before':b[n]['version'],'after':d[n]['version']} for n in changes],'active_edges':[list(x) for x in sorted(edges)],'sdist_only':[n for n in sorted(ns) if 'sdist' in d[n] and not d[n].get('wheels')]}
check=json.loads((a/'root-lock-check-online-20261029.result.json').read_text());assert check['exit_code']==0 and check['before_lock_sha256']==check['seed_or_result_sha256']==sha(a/'candidate/backend/uv.lock');report['root_online_check']=check
report['offline_check']=json.loads((a/'lock-check-offline.result.json').read_text());report['offline_error']=(a/'lock-check-offline.stderr').read_text();assert report['offline_check']['exit_code']!=0
report['complete_whl_files_in_candidate_cache']=[str(f.relative_to(a)) for f in (a/'uv-cache').rglob('*.whl')];report['official_index_sha256']=sha(old/'torch-cpu-index.html');report['full_wheel_bytes_independently_verified']=False
(p/'receipt.json').write_text(json.dumps(report,indent=2));print('Independent CPU lock/graph/source/URL/index/hash-declaration/root-check assertions passed; runtime133/all158; whole-wheel verification NOT established')
