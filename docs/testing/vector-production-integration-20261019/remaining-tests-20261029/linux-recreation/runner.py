import json,hashlib,sys,os,time,importlib.metadata as md
from pathlib import Path
sys.path.insert(0,'/source/backend')
from doc_processor import Chunk
from vector_store import VectorStore
from vector_runtime import SyntheticStorageConfig
from services.document_publication import DocumentPublication
from services.document_catalog import CatalogNotFound
from services.document_runtime import create_pinned_embedding
phase=int(sys.argv[1]); started=time.monotonic()
r=json.loads(Path('/model-receipt.json').read_text())
p={'model':'BAAI/bge-small-zh-v1.5','revision':r['revision'],'dimension':512,'normalize':True,'files_sha256':{k:v['sha256'] for k,v in r['files'].items()}}
control=Path('/fixtures/control.json')
if phase==1:
    c=SyntheticStorageConfig.create()
    control.write_text(json.dumps({'root':str(c.root),'documents':['accept-A','accept-B'],'profile_sha256':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()}))
else: c=SyntheticStorageConfig.from_root(json.loads(control.read_text())['root'])
s=DocumentPublication(VectorStore(persist_dir=str(c.root/'database'),embedding_dim=512,embedding_model=p['model'],synthetic_config=c),c.root/'assets',p)
e=create_pinned_embedding(r['snapshot'],p)
texts={'A1':'第一版独有标识：锅炉检修负责人张三。','A2':'第二版独有标识：汽轮机维护负责人李四。','B':'独立文档乙：变压器巡检负责人王五。'}
checks=[]
def publish(task,doc,key,rev=None):
    text=texts[key]; asset=s.asset_root/(task+'.txt'); asset.write_text(text)
    out=s.publish(task,doc,{'owner_id':'accept-owner','filename':'same.docx'},[Chunk('c00001',text,'text')],e.embed_texts([text]),assets=[{'path':asset.name,'sha256':hashlib.sha256(asset.read_bytes()).hexdigest()}],expected_revision=rev)
    checks.append({'action':task,'result':out});return out
def query(doc,key):
    out=s.search(e.embed_query(texts[key]),allowed_document_ids={doc},top_k=5)
    assert [v['text'] for v in out]==[texts[key]],out
    checks.append({'action':'query','document':doc,'expected':key,'actual_texts':[v['text'] for v in out]})
if phase==1:
    publish('publish-A-v1','accept-A','A1');publish('publish-B','accept-B','B');query('accept-A','A1');query('accept-B','B')
    assert publish('update-A-v2','accept-A','A2',1)['active_revision']==2
    query('accept-A','A2');query('accept-B','B')
elif phase==2:
    query('accept-A','A2');query('accept-B','B')
    with s.catalog() as cat:
        assert cat.get_active('accept-A')['active_revision']==2
        receipt=cat.connection.execute("SELECT status FROM document_tasks WHERE task_id='update-A-v2'").fetchone();assert receipt==('done',)
    checks.append({'action':'catalog-receipt-recovered','revision':2,'receipt':'done'})
    checks.append({'action':'delete-A','result':s.delete('accept-A')})
elif phase==3:
    try:
        with s.catalog() as cat:cat.get_active('accept-A')
    except CatalogNotFound: checks.append({'action':'A-missing','service_exception':'CatalogNotFound','http_equivalent':404})
    else:raise AssertionError('A resurrected')
    assert s.search(e.embed_query(texts['A2']),allowed_document_ids={'accept-A'})==[]
    query('accept-B','B')
assert not os.access('/source/backend/services/document_publication.py',os.W_OK)
assert not os.access('/models/bge-small-zh-v1.5/model.safetensors',os.W_OK)
Path('/evidence/phase-%d.json'%phase).write_text(json.dumps({'phase':phase,'pid':os.getpid(),'uid':os.getuid(),'checks':checks,'seconds':time.monotonic()-started,'profile':p,'root':str(c.root)},ensure_ascii=False,indent=2))
print('PHASE',phase,'PASS',time.monotonic()-started,flush=True)
