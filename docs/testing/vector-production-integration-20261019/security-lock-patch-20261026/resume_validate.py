import hashlib,json,os,pathlib,subprocess,time,tomllib
ROOT=pathlib.Path(__file__).resolve().parent
PYTHON=ROOT/'.venv/Scripts/python.exe'
BASE=pathlib.Path('D:/graghRAG-agent/.tmp/vector-runtime-20261020/derived/python/python.exe')
TARGET=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
env=os.environ.copy(); env['UV_CACHE_DIR']='D:/graghRAG-agent/.tmp/runtime-lock-20261022/uv-cache';env['PYTHONDONTWRITEBYTECODE']='1'
results=json.loads((ROOT/'commands.json').read_text(encoding='utf-8')) if (ROOT/'commands.json').exists() else []
def run(name,args,cwd=ROOT):
    start=time.time()
    with (ROOT/(name+'.log')).open('w',encoding='utf-8') as log:
        p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
    result={'name':name,'command':list(map(str,args)),'cwd':str(cwd),'exit':p.returncode,'elapsed':time.time()-start}
    results.append(result);(ROOT/'commands.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(name,p.returncode,flush=True)
    return p.returncode
assert run('install-local',['uv','pip','install','--python',PYTHON,'--no-deps','-e',ROOT/'langextract'])==0
assert run('pip-check',['uv','pip','check','--python',PYTHON])==0
lock=tomllib.loads((ROOT/'backend/uv.lock').read_text(encoding='utf-8'))
reqs=sorted({p['name']+'=='+p['version'] for p in lock['package'] if 'registry' in p.get('source',{})})
(ROOT/'all-lock-requirements.txt').write_text('\n'.join(reqs)+'\n',encoding='utf-8')
run('pip-audit-all-lock',[PYTHON,'-B','-m','pip_audit','-r',ROOT/'all-lock-requirements.txt','--disable-pip','--no-deps','--format','json','--output',ROOT/'pip-audit-all-lock.json','--cache-dir',ROOT/'audit-cache','--progress-spinner','off'])
run('pip-audit-installed',[PYTHON,'-B','-m','pip_audit','--format','json','--output',ROOT/'pip-audit-installed.json','--cache-dir',ROOT/'audit-cache-installed','--progress-spinner','off'])
env['PYTHONPATH']=str(TARGET/'backend')+';'+str(TARGET/'langextract')
env['PYTHON_DOTENV_DISABLED']='1';env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
run('filelock-real-regression',[PYTHON,'-B','-m','pytest',TARGET/'backend/tests/test_vector_ingest_recovery.py',TARGET/'backend/tests/test_vector_publication_backup.py',TARGET/'backend/tests/test_vector_document_publication.py',TARGET/'backend/tests/test_vector_startup_recovery.py','-q','-ra','-p','no:cacheprovider','--basetemp',ROOT/'test-temp','--junitxml',ROOT/'junit.xml'],TARGET/'backend')


