import subprocess,pathlib,json,time
p=pathlib.Path(r'D:/graghRAG-agent/.tmp/native-torch-scope-review-20261029/pure-conversion');name='graphrag-uv-pure-20261029'
a=['docker','run','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534','--cpus','2','--memory','2g','--pids-limit','64','--tmpfs','/tmp:rw,nosuid,size=134217728,mode=1777','--mount',f'type=bind,src={p / "probe.py"},dst=/probe.py,readonly','--env','PYTHONDONTWRITEBYTECODE=1','sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83','/opt/graphrag-cpu/venv/bin/python','/probe.py']
t=time.monotonic();r={'argv':a,'timeout':30}
try:
 c=subprocess.run(a,capture_output=True,timeout=30);(p/'stdout.json').write_bytes(c.stdout);(p/'stderr.log').write_bytes(c.stderr);r['exit']=c.returncode
except subprocess.TimeoutExpired as e:
 r['timeout_hit']=True;subprocess.run(['docker','kill',name],capture_output=True,timeout=10)
r['seconds']=time.monotonic()-t
c=subprocess.run(['docker','inspect',name],capture_output=True,timeout=10);(p/'inspect.json').write_bytes(c.stdout);r['inspect_exit']=c.returncode
(p/'command.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
