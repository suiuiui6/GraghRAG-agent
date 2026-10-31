import pathlib,hashlib,json,tarfile,tomllib,ast
p=pathlib.Path(__file__).parent;a=p.parent/'linux-cpu-sdist-source-review-20261029';pre=p.parent/'linux-cpu-install-preflight-20261029';sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();lock=tomllib.loads((p.parent/'linux-cpu-direct-url-20261028/candidate/backend/uv.lock').read_text());pkgs={v['name']:v for v in lock['package']};report={'network_requests':0,'build_hooks_executed':False,'inputs':{str(f):sha(f) for f in [pre/'PLAN.md',pre/'receipt.json',a/'receipt.json',a/'oss2-retry1-receipt.json']},'artifacts':{}}
for name,filename in [('crcmod','crcmod-1.7.tar.gz'),('oss2','oss2-2.19.1-retry1.tar.gz')]:
 f=a/filename;s=pkgs[name]['sdist'];assert sha(f)=='dc7051a0db5f2bd48665a990d3ec1cc305a466a77358ca4492826f41f283601e' if name=='crcmod' else sha(f)=='a8ab9ee7eb99e88a7e1382edc6ea641d219d585a7e074e3776e9dec9473e59c1';assert 'sha256:'+sha(f)==s['hash'] and f.stat().st_size==s['size']
 row={'path':str(f),'sha256':sha(f),'bytes':f.stat().st_size,'members':[],'review_files':{}}
 with tarfile.open(f) as t:
  for m in t.getmembers():
   q=pathlib.PurePosixPath(m.name);assert not q.is_absolute() and '..' not in q.parts and '\\' not in m.name and ':' not in m.name and (m.isdir() or m.isfile()),m.name
   if not m.isfile():continue
   data=t.extractfile(m).read();row['members'].append({'path':m.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
   relative='/'.join(q.parts[1:])
   selected=relative in ['setup.py','setup.cfg','pyproject.toml','python3/src/_crcfunext.c','python3/src/crcmod.c','python3/crcmod/crcmod.py','python3/crcmod/predefined.py','python3/test.py','oss2/__init__.py','oss2/crc64_combine.py']
   if selected:
    dst=p/(name+'-'+relative.replace('/','_')+'.txt');dst.write_bytes(data);row['review_files'][relative]={'file':dst.name,'sha256':hashlib.sha256(data).hexdigest()}
 row['pyproject_present']=any(x['path'].endswith('/pyproject.toml') for x in row['members']);report['artifacts'][name]=row
report['setuptools_runtime_lock']=pkgs['setuptools']['version'];report['wheel_in_runtime_lock']='wheel' in pkgs
(p/'receipt.json').write_text(json.dumps(report,indent=2));print({k:{'sha256':v['sha256'],'members':len(v['members']),'files':list(v['review_files'])} for k,v in report['artifacts'].items()})
