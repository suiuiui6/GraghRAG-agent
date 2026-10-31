import json,pathlib,subprocess,time
root=pathlib.Path(__file__).resolve().parent
py=str(root/'.venv/Scripts/python.exe')
records=[]
for i in range(2):
 start=time.monotonic(); p=subprocess.run([py,'-B','-c','import time; t=time.monotonic(); import torch; print("torch",time.monotonic()-t,flush=True); t=time.monotonic(); import sentence_transformers; print("sentence_transformers",time.monotonic()-t,flush=True)'],capture_output=True,text=True)
 record={'run':i+1,'fresh_process':True,'exit':p.returncode,'seconds':time.monotonic()-start,'stdout':p.stdout,'stderr':p.stderr};records.append(record); print(json.dumps(record),flush=True)
(root/'import-timing.json').write_text(json.dumps(records,indent=2))
assert all(r['exit']==0 for r in records)
