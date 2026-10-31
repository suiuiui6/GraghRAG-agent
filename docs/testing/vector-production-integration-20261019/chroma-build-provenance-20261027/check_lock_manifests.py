import concurrent.futures, datetime, hashlib, io, json, pathlib, subprocess, tarfile, tomllib

root = pathlib.Path(__file__).resolve().parent
lock = tomllib.loads((root / 'original-Cargo.lock').read_text(encoding='utf-8'))
packages = [p for p in lock['package'] if p.get('source', '').startswith('registry+') and any(d.startswith('serde_json') for d in p.get('dependencies', []))]

def check(p):
    name, version = p['name'], p['version']
    dest = root / 'crates' / f'{name}-{version}.crate'
    dest.parent.mkdir(exist_ok=True)
    url = f'https://static.crates.io/crates/{name}/{name}-{version}.crate'
    args = ['curl.exe', '--silent', '--show-error', '--location', '--connect-timeout', '8', '--max-time', '35', '--output', str(dest), '--write-out', '%{http_code}', url]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=40)
    r = {'name': name, 'version': version, 'url': url, 'command': args, 'exit': proc.returncode, 'http': proc.stdout, 'stderr': proc.stderr}
    if dest.exists():
        r['sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
        r['matches_original_lock_checksum'] = r['sha256'] == p.get('checksum')
        if r['matches_original_lock_checksum']:
            with tarfile.open(dest) as tf:
                data = tf.extractfile(f'{name}-{version}/Cargo.toml').read()
            (root / 'crates' / f'{name}-{version}.Cargo.toml').write_bytes(data)
            d = tomllib.loads(data.decode())
            r['feature_declarations'] = d.get('features', {})
            r['serde_sections'] = {}
            for section in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                for k, v in d.get(section, {}).items():
                    if k == 'serde_json' or v.get('package') == 'serde_json':
                        r['serde_sections'][section + '.' + k] = v
            for target, sections in d.get('target', {}).items():
                for section in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                    for k, v in sections.get(section, {}).items():
                        if k == 'serde_json' or v.get('package') == 'serde_json':
                            r['serde_sections'][target + '.' + section + '.' + k] = v
            r['special_feature_mentions'] = [line for line in data.decode().splitlines() if any(f in line for f in ['float_roundtrip', 'arbitrary_precision', 'unbounded_depth'])]
    return r

records = []
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for record in pool.map(check, packages):
        records.append(record)
        print(record['name'], record['version'], record['exit'], record['http'], record.get('matches_original_lock_checksum'), record.get('special_feature_mentions'), flush=True)
        (root / 'third-party-manifest-results.json').write_text(json.dumps({'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'records': records}, indent=2), encoding='utf-8')
