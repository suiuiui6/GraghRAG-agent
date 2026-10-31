import base64, concurrent.futures, hashlib, json, pathlib, subprocess, tarfile, tomllib
root = pathlib.Path(__file__).resolve().parent
old = root.parent / 'chroma-build-provenance-20261026'
tree = {x['path']: x for x in json.loads((old / 'github-tree.json').read_text(encoding='utf-8'))['tree'] if x['path'].endswith('Cargo.toml')}
original = {}
with tarfile.open(old / 'chromadb-1.5.9.tar.gz') as tf:
    for m in tf.getmembers():
        if m.name.endswith('Cargo.toml'):
            name = m.name.split('/', 1)[1]; data = tf.extractfile(m).read()
            if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == tree.get(name, {}).get('sha'):
                original[name] = data
original['Cargo.toml'] = (old / 'Cargo.toml').read_bytes()
missing = [(name, value) for name, value in tree.items() if name not in original]
def fetch(pair):
    name, entry = pair; url = 'https://api.github.com/repos/chroma-core/chroma/git/blobs/' + entry['sha']
    dest = root / 'original-workspace' / (name.replace('/', '__') + '.api.json'); dest.parent.mkdir(exist_ok=True)
    args = ['curl.exe', '--silent', '--show-error', '--location', '--connect-timeout', '5', '--max-time', '20', '--output', str(dest), '--write-out', '%{http_code}', url]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=25)
    r = {'path': name, 'url': url, 'exit': proc.returncode, 'http': proc.stdout, 'stderr': proc.stderr, 'command': args}
    if proc.stdout == '200':
        obj = json.loads(dest.read_text(encoding='utf-8')); data = base64.b64decode(obj['content'])
        r['git_blob_sha1_matches'] = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == entry['sha']
        if r['git_blob_sha1_matches']: original[name] = data
    return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(fetch, missing))
records = []
for name, data in sorted(original.items()):
    (root / 'original-workspace' / name.replace('/', '__')).write_bytes(data)
    d = tomllib.loads(data.decode()); records.append({'path': name, 'git_blob_matches': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == tree[name]['sha'], 'sha256': hashlib.sha256(data).hexdigest(), 'special_mentions': [line for line in data.decode().splitlines() if any(f in line for f in ['float_roundtrip', 'arbitrary_precision', 'unbounded_depth'])]})
(root / 'original-workspace-results.json').write_text(json.dumps({'fetches': results, 'expected_manifest_count': len(tree), 'actual_manifest_count': len(records), 'records': records}, indent=2), encoding='utf-8')
print('count',len(records),'expected',len(tree)); print('fetches',[(r['path'],r['http']) for r in results]); print('mismatch',[r for r in records if not r['git_blob_matches']]);print('special',[r for r in records if r['special_mentions']])
