import sys,ssl,zlib,pyexpat,sqlite3,json,hashlib,pathlib,importlib.metadata as md
base=pathlib.Path(sys.base_prefix)
site=pathlib.Path(sys.prefix)/'Lib/site-packages'
items={}
for rel in ['python312.dll','DLLs/pyexpat.pyd','DLLs/_ssl.pyd','DLLs/sqlite3.dll','Lib/mimetypes.py','Lib/tarfile.py']:
 p=base/rel
 if p.is_file(): items[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}
dlls={}
for dirname in ['numpy.libs','scipy.libs','scikit_learn.libs','torch/lib']:
 d=site/dirname
 dlls[dirname]=[{'name':p.name,'bytes':p.stat().st_size} for p in d.glob('*.dll')]
import numpy as np
cfg=np.__config__.show(mode='dicts')
r={'python':sys.version,'prefix':sys.prefix,'base_prefix':str(base),'openssl':ssl.OPENSSL_VERSION,'expat':pyexpat.EXPAT_VERSION,'zlib':zlib.ZLIB_RUNTIME_VERSION,'sqlite':sqlite3.sqlite_version,'numpy':np.__version__,'numpy_config':cfg,'runtime_files':items,'dll_inventory_top_level_only':dlls,'installed_selected':{n:md.version(n) for n in ['numpy','scipy','scikit-learn','torch','safetensors','tokenizers','sentence-transformers']}}
for p in (site/'numpy.libs').glob('*.dll'):r['runtime_files']['numpy.libs/'+p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}
pathlib.Path('D:/graghRAG-agent/.tmp/native-advisory-triage-20261027/actual-metadata.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps({k:r[k] for k in ['python','openssl','expat','zlib','sqlite','numpy','installed_selected','dll_inventory_top_level_only']},indent=2))
