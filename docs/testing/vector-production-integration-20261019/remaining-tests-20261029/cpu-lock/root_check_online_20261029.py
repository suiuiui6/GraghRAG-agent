import pathlib,json,subprocess,os,time,hashlib,datetime,sys
r=pathlib.Path(__file__).parent
prefix='root-lock-check-online-20261029'
exe='D:/Python/Scripts/uv.exe'
args=[exe,'lock','--project',str(r/'candidate/backend'),'--python','C:/Users/14156/AppData/Local/Programs/Python/Python312/python.exe','--no-python-downloads','--cache-dir',str(r/'uv-cache'),'--system-certs','--default-index','https://pypi.org/simple','--verbose']
for name in json.loads((r/'no-build-packages.json').read_text()):args+=['--no-build-package',name]
env=os.environ.copy()
for k in list(env):
    if k.startswith('UV_'):env.pop(k)
settings={'UV_HTTP_TIMEOUT':'20','UV_HTTP_RETRIES':'1','UV_CONCURRENT_DOWNLOADS':'4','UV_NO_PROGRESS':'1','UV_NO_ENV_FILE':'1','UV_PYTHON_DOWNLOADS':'never'}
if 'offline' in prefix:args+=['--offline']
if 'check' in prefix:args+=['--check']
env.update(settings)
command={'argv':args,'env_explicit':settings,'inherited_UV_variables_removed':True,'deadline_seconds':88,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'note':'Normal dependency resolver. Existing verified oss2/crcmod cached metadata; no installation. Only private directory writable. Source URL contains official SHA256.'}
(r/(prefix+'.command.json')).write_text(json.dumps(command,indent=2))
before_hash=hashlib.sha256((r/'candidate/backend/uv.lock').read_bytes()).hexdigest()
start=time.monotonic()
with (r/(prefix+'.stdout')).open('wb') as out,(r/(prefix+'.stderr')).open('wb') as err:
    p=subprocess.Popen(args,env=env,stdout=out,stderr=err,cwd=r/'candidate/backend')
    try:code=p.wait(timeout=88)
    except subprocess.TimeoutExpired:p.kill();p.wait();code=124
(r/(prefix+'.result.json')).write_text(json.dumps({'before_lock_sha256':before_hash,'exit_code':code,'elapsed_seconds':time.monotonic()-start,'seed_or_result_sha256':hashlib.sha256((r/'candidate/backend/uv.lock').read_bytes()).hexdigest()},indent=2))
print((r/(prefix+'.result.json')).read_text())
print((r/(prefix+'.stderr')).read_text(errors='replace')[-14000:])
