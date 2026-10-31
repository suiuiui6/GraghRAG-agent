import concurrent.futures,hashlib,importlib.metadata,json,pathlib,shutil,time
ROOT=pathlib.Path(__file__).resolve().parent
OLD=pathlib.Path('D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Lib/site-packages')
NEW=ROOT/'.venv/Lib/site-packages'
skip=set(); names={'filelock','opentelemetry-api','setuptools','langextract'}
for dist in importlib.metadata.distributions(path=[str(OLD)]):
    if dist.metadata['Name'].lower().replace('_','-') in names:
        for file in dist.files or []:
            p=(OLD/file).resolve()
            if p.is_relative_to(OLD):skip.add(p.relative_to(OLD).as_posix())
hashes={};before=time.time()
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def copy_one(p):
    rel=p.relative_to(OLD).as_posix()
    if rel in skip:return None
    digest=sha(p);destination=NEW/rel;destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists() or sha(destination)!=digest:shutil.copyfile(p,destination)
    assert sha(destination)==digest,rel
    return rel,digest
files=(p for p in OLD.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for item in pool.map(copy_one,files):
        if item:hashes[item[0]]=item[1]
(ROOT/'copied-unchanged-files.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
receipt={'source':str(OLD),'destination':str(NEW),'copied_verified_files':len(hashes),'excluded_distributions':sorted(names),'pyc':'not copied','elapsed':time.time()-before,'limitation':'Verified copy of existing installed payload, not a clean complete reinstall'}
(ROOT/'copied-runtime-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt),flush=True)
