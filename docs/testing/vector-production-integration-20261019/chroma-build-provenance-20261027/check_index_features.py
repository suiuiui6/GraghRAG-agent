import base64, concurrent.futures, datetime, hashlib, json, pathlib, subprocess, tomllib
root = pathlib.Path(__file__).resolve().parent
lock = tomllib.loads((root / 'original-Cargo.lock').read_text(encoding='utf-8'))
packages = [p for p in lock['package'] if p.get('source', '').startswith('registry+') and any(d.startswith('serde_json') for d in p.get('dependencies', []))]
def check(p):
    name = p['name']; prefix = name[:2] + '/' + name[2:4] if len(name) > 3 else ('3/' + name[0] if len(name) == 3 else str(len(name)))
    url = 'https://api.github.com/repos/rust-lang/crates.io-index/contents/' + prefix + '/' + name
    dest = root / 'index' / (name + '.json'); dest.parent.mkdir(exist_ok=True)
    args = ['curl.exe', '--silent', '--show-error', '--location', '--connect-timeout', '5', '--max-time', '20', '--output', str(dest), '--write-out', '%{http_code}', url]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=25)
    r = {'name': name, 'version': p['version'], 'url': url, 'command': args, 'exit': proc.returncode, 'http': proc.stdout, 'stderr': proc.stderr}
    if proc.stdout == '200':
        obj = json.loads(dest.read_text(encoding='utf-8')); content = base64.b64decode(obj['content'])
        r['index_git_blob'] = obj['sha']; r['index_content_bytes'] = len(content)
        entries = [json.loads(x) for x in content.splitlines() if x]
        found = [e for e in entries if e['vers'] == p['version']]
        if len(found) == 1:
            e = found[0]; r['entry'] = e; r['matches_original_lock_checksum'] = e['cksum'] == p['checksum']
            r['serde_dependencies'] = [d for d in e['deps'] if d['name'] == 'serde_json' or d.get('package') == 'serde_json']
            r['special_feature_mentions'] = [f for f in ['float_roundtrip', 'arbitrary_precision', 'unbounded_depth'] if f in json.dumps(e)]
    return r
records = []
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    for record in pool.map(check, packages):
        records.append(record); print(record['name'], record['http'], record.get('matches_original_lock_checksum'), record.get('special_feature_mentions'), flush=True)
        (root / 'index-feature-results.json').write_text(json.dumps({'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'records': records}, indent=2), encoding='utf-8')
