import datetime, hashlib, json, pathlib, tarfile, tomllib
root = pathlib.Path(__file__).resolve().parent
old = root.parent / 'chroma-build-provenance-20261026'
wheel = old / 'chromadb-1.5.9-cp39-abi3-win_amd64.whl'
expected = '4fd0b560e56761b7f3cb4d5c6205fd5f20814484b4a3e4e9af9038c2b428fc6c'
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == expected
release = json.loads((old / 'pypi-release.json').read_text(encoding='utf-8'))
for name in [wheel.name, 'chromadb-1.5.9.tar.gz']:
    entry = next(e for e in release['urls'] if e['filename'] == name)
    assert hashlib.sha256((old / name).read_bytes()).hexdigest() == entry['digests']['sha256']
verified = json.loads((root / 'gh-verification-network.json').read_text(encoding='utf-8-sig'))
assert len(verified) == 1
v = verified[0]['verificationResult']; certificate = v['signature']['certificate']
assert certificate['sourceRepositoryDigest'] == '11f3c7435e71024aa0a2b53710a28d3289d922d1'
assert certificate['sourceRepositoryRef'] == 'refs/tags/1.5.9'
assert certificate['issuer'] == 'https://token.actions.githubusercontent.com'
assert certificate['subjectAlternativeName'] == 'https://github.com/chroma-core/chroma/.github/workflows/_build_release_pypi.yml@refs/tags/1.5.9'
assert v['statement']['subject'][0]['digest']['sha256'] == expected
assert v['verifiedTimestamps']
tree = json.loads((old / 'github-tree.json').read_text(encoding='utf-8'))['tree']
lock_bytes = (root / 'original-Cargo.lock').read_bytes()
assert hashlib.sha1(b'blob ' + str(len(lock_bytes)).encode() + b'\0' + lock_bytes).hexdigest() == next(x['sha'] for x in tree if x['path'] == 'Cargo.lock')
lock = tomllib.loads(lock_bytes.decode()); consumers = [p for p in lock['package'] if any(d.startswith('serde_json') for d in p.get('dependencies', []))]
indices = json.loads((root / 'index-feature-results.json').read_text(encoding='utf-8'))['records']
assert len(indices) == 30
assert all(p['http'] == '200' and p['matches_original_lock_checksum'] and not p['special_feature_mentions'] for p in indices)
workspace = json.loads((root / 'original-workspace-results.json').read_text(encoding='utf-8'))
assert workspace['expected_manifest_count'] == workspace['actual_manifest_count'] == 37
assert all(p['git_blob_matches'] and not p['special_mentions'] for p in workspace['records'])
local_names = {tomllib.loads(p.read_text(encoding='utf-8')).get('package', {}).get('name') for p in (root / 'original-workspace').glob('*Cargo.toml')}
local = [p for p in consumers if not p.get('source')]
assert len(local) == 20 and all(p['name'] in local_names for p in local)
git = [p for p in consumers if p.get('source', '').startswith('git+')]
assert len(git) == 1 and git[0]['name'] == 'gcloud-auth'
gcloud = json.loads((root / 'gcloud-results.json').read_text(encoding='utf-8'))
assert len(gcloud) == 2 and all(p['http'] == '200' and p['git_blob_matches'] for p in gcloud)
assert not any(feature in (root / 'gcloud-auth.Cargo.toml').read_text(encoding='utf-8') for feature in ['float_roundtrip', 'arbitrary_precision', 'unbounded_depth'])
assert tomllib.loads((root / 'gcloud-auth.Cargo.toml').read_text(encoding='utf-8'))['dependencies']['serde_json'] == {'version': '1.0'}
inputs = {}
for folder in [root, old]:
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix != '.pyc' and p.name != 'evidence-verification.json' and 'crates' not in p.parts:
            inputs[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
report = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit': 0, 'wheel_sha256': expected, 'sigstore_cryptographic_verification': 'gh attestation verify exit 0; actual gh output retained', 'original_lock_direct_serde_json_consumers': len(consumers), 'registry_consumers_exact_checksum_matches': len(indices), 'workspace_consumers_covered': len(local), 'git_consumers_covered': len(git), 'original_workspace_manifests_bound_to_git_blobs': 37, 'special_feature_requests_found': 0, 'limits': ['This is a declared source/build configuration argument, not a captured original rustc feature graph.', 'No original Chroma code was executed.', 'No compatibility gate, contract, or C worktree file was changed.'], 'inputs_sha256': inputs}
(root / 'evidence-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k != 'inputs_sha256'},indent=2))
