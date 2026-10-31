import concurrent.futures,hashlib,json,pathlib,sys,time
root=pathlib.Path(__file__).resolve().parent
site=root/'.venv/Lib/site-packages'
paths=sorted(site.rglob('*.py'))
def hashfile(p):return str(p.relative_to(site)).replace('\\','/'),hashlib.sha256(p.read_bytes()).hexdigest()
start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: hashes=dict(pool.map(hashfile,paths))
(root/(sys.argv[1]+'-source-hashes.json')).write_text(json.dumps(hashes,indent=2))
print(len(hashes),'Python sources hashed in',time.monotonic()-start,flush=True)
