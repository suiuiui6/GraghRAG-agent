"""Local Windows libuv backport recipe; receipts require independent human review."""
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'manifest.json'
LOCKED_BASE_VERSION = '1.40.0'
LOCKED_BASE_COMMIT = '4e69e333252693bd82d6338d6124f0416538dbfc'
LOCKED_REFERENCE_SHA256 = 'fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8'
LOCKED_PATCH_SHA256 = 'a20128ca27cf079ae3ed8d449a4daecaed45b14f41a142a09592eada918444e1'
LOCKED_TARGET = 'x86_64-pc-windows-msvc'
LOCKED_UPSTREAM_COMMITS = [
    'b7466e31e4bee160d82a68fca11b1f61d46debae',
    '0f2d7e784a256b54b2385043438848047bc2a629',
    '3530bcc30350d4a6ccf35d2f7b33e23292b9de70',
    'e0327e1d508b8207c9150b6e582f0adf26213c39',
]
LOCKED_CHANGED_FILES = ['src/idna.c', 'test/test-idna.c', 'test/test-list.h']
LOCKED_TOOLCHAIN = {
    'cmake': '4.2.3',
    'msvc': '19.50.35728',
    'vctools': '14.50.35717',
    'generator': 'NMake Makefiles',
}
LOCKED_SOURCE = {
    'kind': 'git-checkout',
    'network': 'no-network-commands',
    'base_commit': LOCKED_BASE_COMMIT,
}
LOCKED_BUILD = {
    'generator': 'NMake Makefiles',
    'configuration': 'Release',
    'artifact': 'uv.dll',
}
LOCKED_TEST_CONTRACT = {
    'dynamic': {'tests': 402},
    'static': {'tests': 405},
}
FORBIDDEN_BUILD_ENV = (
    'CMAKE_TOOLCHAIN_FILE', 'CMAKE_PREFIX_PATH', 'CMAKE_GENERATOR', 'CC', 'CXX',
    'CL', '_CL_', 'LINK', '_LINK_', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS',
    'VCPKG_ROOT', 'VCPKG_INSTALLATION_ROOT', 'VCPKG_DEFAULT_TRIPLET',
)

LOCKED_PLATFORM_SKIPS = {
    'eintr_handling', 'fs_event_watch_file_root_dir', 'fs_partial_read', 'fs_partial_write',
    'pipe_set_non_blocking', 'spawn_empty_env', 'spawn_stdout_and_stderr_to_file2',
    'spawn_stdout_and_stderr_to_file_swap',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_build_overrides():
    if any(os.environ.get(name) for name in FORBIDDEN_BUILD_ENV):
        raise SystemExit('unsupported build environment override')


def load_manifest():
    try:
        value = json.loads(MANIFEST.read_text(encoding='utf-8'))
        patch = (ROOT / value['patch']).resolve()
        patch.relative_to(ROOT.resolve())
        valid = (
            value.get('schema') == 1
            and value.get('target') == LOCKED_TARGET
            and value.get('base_version') == LOCKED_BASE_VERSION
            and value.get('base_commit') == LOCKED_BASE_COMMIT
            and value.get('reference_sha256') == LOCKED_REFERENCE_SHA256
            and value.get('upstream_commits') == LOCKED_UPSTREAM_COMMITS
            and value.get('changed_files') == LOCKED_CHANGED_FILES
            and value.get('patch') == 'patches/idna-backport.patch'
            and value.get('patch_sha256') == LOCKED_PATCH_SHA256 == sha(patch)
            and value.get('source') == LOCKED_SOURCE
            and value.get('build') == LOCKED_BUILD
            and value.get('toolchain') == LOCKED_TOOLCHAIN
            and value.get('test_contract') == LOCKED_TEST_CONTRACT
        )
    except (OSError, KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise SystemExit('invalid locked backport manifest')
    return value


def recipe_commands(source, build_dir, *, git='git', cmake='cmake'):
    """Return the offline source-to-candidate command recipe."""
    manifest = load_manifest()
    source = str(Path(source).resolve())
    build_dir = str(Path(build_dir).resolve())
    patch = str((ROOT / manifest['patch']).resolve())
    return [
        [git, '-C', source, 'rev-parse', 'HEAD'],
        [git, '-C', source, 'status', '--porcelain', '--untracked-files=all', '--ignored=matching'],
        [git, '-C', source, 'apply', '--check', patch],
        [git, '-C', source, 'apply', '--whitespace=error-all', patch],
        [cmake, '--version'],
        ['cl', '/Bv', '/c', str(Path(build_dir).parent / 'compiler-probe.c'), '/Fo' + str(Path(build_dir).parent / 'compiler-probe.obj')],
        ['nmake', '/?'],
        [cmake, '-S', source, '-B', build_dir, '-G', manifest['build']['generator'],
         '-DCMAKE_BUILD_TYPE=' + manifest['build']['configuration'], '-DBUILD_TESTING=ON',
         '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
         '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
         '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
         '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF'],
        [cmake, '--build', build_dir, '--config', manifest['build']['configuration']],
    ]


def _run_recipe_command(command, cwd, commands):
    value = subprocess.run(
        command,
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    commands.append(command)
    return value.stdout + value.stderr


def _tree_facts(source):
    facts = {}
    for path in sorted(Path(source).rglob('*')):
        relative = path.relative_to(source)
        if relative.parts[0] == '.git':
            continue
        attributes = getattr(path.lstat(), 'st_file_attributes', 0)
        if path.is_symlink() or attributes & 0x400:
            raise SystemExit('source checkout must not contain reparse points')
        if path.is_file():
            facts[relative.as_posix()] = sha(path)
    return facts


def run_recipe(source, staging, *, git='git', cmake='cmake'):
    """Build using local commands. OS network isolation is a caller responsibility."""
    manifest = load_manifest()
    check_build_overrides()
    source = Path(source).resolve()
    staging = Path(staging).resolve()
    if not source.is_dir():
        raise SystemExit('source checkout is missing')
    if staging.exists() or staging.is_relative_to(source):
        raise SystemExit('use a fresh build staging directory outside source')
    commands = []
    head = _run_recipe_command([git, '-C', str(source), 'rev-parse', 'HEAD'], source, commands)
    if head.strip() != manifest['base_commit']:
        raise SystemExit('source checkout must match locked base commit')
    status = _run_recipe_command(
        [git, '-C', str(source), 'status', '--porcelain', '--untracked-files=all', '--ignored=matching'],
        source, commands,
    )
    if status.strip():
        raise SystemExit('source checkout must be clean')
    original = _tree_facts(source)
    tools = {}
    for name, executable in (('git', git), ('cmake', cmake), ('cl', 'cl'), ('nmake', 'nmake')):
        resolved = shutil.which(executable)
        if resolved is None:
            raise SystemExit('required local build tool is missing: ' + name)
        tools[name] = {'path': str(Path(resolved).resolve()), 'sha256': sha(resolved)}
    if manifest['toolchain']['vctools'] not in Path(tools['cl']['path']).parts:
        raise SystemExit('unexpected VC Tools directory')
    staging.mkdir(parents=True)
    working, build_dir = staging / 'source', staging / 'build'
    # Failures preserve private staging for diagnosis. Never reuse that directory.
    shutil.copytree(source, working)
    if _tree_facts(working) != original or _tree_facts(source) != original:
        raise SystemExit('source changed during copy')
    patch = str((ROOT / manifest['patch']).resolve())
    _run_recipe_command([tools['git']['path'], '-C', str(working), 'apply', '--check', patch], working, commands)
    _run_recipe_command([tools['git']['path'], '-C', str(working), 'apply', '--whitespace=error-all', patch], working, commands)
    patched = _tree_facts(working)
    cmake_version = _run_recipe_command([tools['cmake']['path'], '--version'], working, commands)
    if re.match(r'cmake version ' + re.escape(manifest['toolchain']['cmake']) + r'(?:[-\s]|$)', cmake_version) is None:
        raise SystemExit('unexpected CMake identity')
    probe = staging / 'compiler-probe.c'
    probe.write_text('int libuv_compiler_probe(void) { return 0; }\n', encoding='ascii')
    compiler_version = _run_recipe_command(
        [tools['cl']['path'], '/Bv', '/c', str(probe), '/Fo' + str(staging / 'compiler-probe.obj')], staging, commands)
    if manifest['toolchain']['msvc'] not in compiler_version:
        raise SystemExit('unexpected MSVC identity')
    nmake_version = _run_recipe_command([tools['nmake']['path'], '/?'], working, commands)
    if manifest['toolchain']['msvc'].replace('19.', '14.', 1) not in nmake_version:
        raise SystemExit('unexpected NMake identity')
    configure = [tools['cmake']['path'], '-S', str(working), '-B', str(build_dir),
        '-G', manifest['build']['generator'], '-DCMAKE_BUILD_TYPE=' + manifest['build']['configuration'],
        '-DBUILD_TESTING=ON', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
        '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
        '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
        '-DCMAKE_C_COMPILER=' + tools['cl']['path'], '-DCMAKE_MAKE_PROGRAM=' + tools['nmake']['path']]
    _run_recipe_command(configure, working, commands)
    _run_recipe_command([tools['cmake']['path'], '--build', str(build_dir), '--config', manifest['build']['configuration']], working, commands)
    candidates = sorted(build_dir.rglob(manifest['build']['artifact']))
    if len(candidates) != 1:
        raise SystemExit('expected exactly one built libuv artifact')
    if _tree_facts(source) != original or _tree_facts(working) != patched:
        raise SystemExit('source changed during build')
    if any(sha(tool['path']) != tool['sha256'] for tool in tools.values()):
        raise SystemExit('build tool changed during build')
    result = {'schema': 1, 'manifest_sha256': sha(MANIFEST), 'patch_sha256': sha(ROOT / manifest['patch']),
        'build_script_sha256': sha(Path(__file__)), 'base_commit': manifest['base_commit'],
        'source_files': original, 'patched_source_files': patched, 'tools': tools,
        'candidate_sha256': sha(candidates[0]), 'commands': commands,
        'tool_versions': {'cmake': cmake_version, 'cl': compiler_version, 'nmake': nmake_version}}
    (staging / 'build-run.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return candidates[0], commands


def compare_facts(candidate, reference):
    manifest = load_manifest()
    fields = ('machine', 'exports', 'dependencies', 'loop_size', 'handle_sizes', 'req_sizes')
    valid = (
        candidate.get('version') == manifest['base_version']
        and reference.get('version') == manifest['base_version']
        and candidate.get('machine') == 'x64'
        and all(candidate.get(field) == reference.get(field) for field in fields)
        and bool(candidate.get('exports'))
    )
    if not valid:
        raise SystemExit('candidate does not preserve reviewed ABI')
    return {
        'version': candidate['version'],
        'exports': len(candidate['exports']),
        'loop_size': candidate['loop_size'],
    }


def _reviewed_identity_error():
    raise SystemExit('reviewed build identity does not match')


def _valid_test_evidence(tests, manifest):
    if not isinstance(tests, dict) or set(tests) != set(manifest['test_contract']):
        return False
    return all(
        isinstance(details, dict)
        and details.get('tests') == manifest['test_contract'][name]['tests']
        and details.get('exit') == 0
        and isinstance(details.get('skip_names'), list)
        and all(isinstance(name, str) and name in LOCKED_PLATFORM_SKIPS for name in details['skip_names'])
        and details.get('skipped') == len(set(details['skip_names'])) == len(details['skip_names'])
        and re.fullmatch(r'[0-9a-f]{64}', details.get('log_sha256', '')) is not None
        for name, details in tests.items()
    )


def create_receipt(staging, candidate, reference, candidate_facts, reference_facts, tests, commands):
    staging = Path(staging).resolve()
    candidate = Path(candidate).resolve()
    reference = Path(reference).resolve()
    receipt_path = staging / 'build-receipt.json'
    if receipt_path.exists() or not candidate.is_relative_to(staging):
        raise SystemExit('use a fresh build staging directory')
    manifest = load_manifest()
    if sha(reference) != manifest['reference_sha256']:
        raise SystemExit('reference identity does not match locked Torch DLL')
    compatibility = compare_facts(candidate_facts, reference_facts)
    if not _valid_test_evidence(tests, manifest):
        raise SystemExit('complete libuv tests did not pass')
    build_run = staging / 'build-run.json'
    if not build_run.is_file():
        raise SystemExit('matching local build record is required')
    receipt = {
        'build_run_sha256': sha(build_run),
        'schema': 1,
        'approved': False,
        'target': manifest['target'],
        'base_commit': manifest['base_commit'],
        'upstream_commits': manifest['upstream_commits'],
        'source': manifest['source'],
        'build': manifest['build'],
        'toolchain': manifest['toolchain'],
        'test_contract': manifest['test_contract'],
        'manifest_sha256': sha(MANIFEST),
        'patch_sha256': sha(ROOT / manifest['patch']),
        'build_script_sha256': sha(Path(__file__)),
        'candidate': {'path': candidate.relative_to(staging).as_posix(), 'sha256': sha(candidate)},
        'reference_sha256': sha(reference),
        'compatibility': compatibility,
        'tests': tests,
        'commands': commands,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return sha(receipt_path)


def install(staging, approval):
    staging = Path(staging).resolve()
    receipt_path = staging / 'build-receipt.json'
    try:
        if re.fullmatch(r'[0-9a-f]{64}', approval) is None or sha(receipt_path) != approval:
            _reviewed_identity_error()
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        manifest = load_manifest()
        candidate_rel = Path(receipt['candidate']['path'])
        candidate = (staging / candidate_rel).resolve()
        valid = (
            receipt.get('schema') == 1
            and receipt.get('build_run_sha256') == sha(staging / 'build-run.json')
            and json.loads((staging / 'build-run.json').read_text(encoding='utf-8')).get('candidate_sha256') == sha(candidate)
            and receipt.get('approved') is False
            and receipt.get('target') == manifest['target']
            and receipt.get('base_commit') == manifest['base_commit']
            and receipt.get('manifest_sha256') == sha(MANIFEST)
            and receipt.get('patch_sha256') == sha(ROOT / manifest['patch'])
            and receipt.get('build_script_sha256') == sha(Path(__file__))
            and receipt.get('upstream_commits') == manifest['upstream_commits']
            and receipt.get('source') == manifest['source']
            and receipt.get('build') == manifest['build']
            and receipt.get('toolchain') == manifest['toolchain']
            and receipt.get('test_contract') == manifest['test_contract']
            and not candidate_rel.is_absolute()
            and candidate.is_relative_to(staging)
            and receipt['candidate'].get('sha256') == sha(candidate)
            and _valid_test_evidence(receipt.get('tests'), manifest)
            and receipt.get('compatibility', {}).get('version') == manifest['base_version']
            and receipt.get('compatibility', {}).get('loop_size') == 464
            and receipt.get('reference_sha256') == manifest['reference_sha256']
        )
        if not valid:
            _reviewed_identity_error()
    except (OSError, KeyError, TypeError, ValueError, SystemExit):
        _reviewed_identity_error()
    root_bin = (ROOT / 'bin').resolve()
    destination = (root_bin / manifest['target']).resolve()
    if not destination.is_relative_to(root_bin):
        raise SystemExit('invalid target destination')
    if destination.exists():
        raise SystemExit('fresh non-serving destination required')
    approved = {
        'schema': 1,
        'approved': True,
        'target': manifest['target'],
        'base_commit': manifest['base_commit'],
        'manifest_sha256': sha(MANIFEST),
        'patch_sha256': manifest['patch_sha256'],
        'build_script_sha256': sha(Path(__file__)),
        'upstream_commits': manifest['upstream_commits'],
        'source': manifest['source'],
        'build': manifest['build'],
        'toolchain': manifest['toolchain'],
        'test_contract': manifest['test_contract'],
        'build_run_sha256': receipt['build_run_sha256'],
        'reviewed_receipt_sha256': approval,
        'candidate_sha256': receipt['candidate']['sha256'],
        'reference_sha256': receipt['reference_sha256'],
        'compatibility': receipt['compatibility'],
        'tests': receipt['tests'],
    }
    serialized = json.dumps(approved, indent=2) + '\n'
    if len(serialized.encode('utf-8')) > 8192:
        raise SystemExit('manifest too large')
    temporary = root_bin / ('.' + manifest['target'] + '.install-' + approval)
    if temporary.exists():
        raise SystemExit('fresh non-serving destination required')
    try:
        temporary.mkdir(parents=True)
        installed_candidate = temporary / manifest['build']['artifact']
        shutil.copyfile(candidate, installed_candidate)
        if sha(installed_candidate) != receipt['candidate']['sha256']:
            raise SystemExit('candidate changed during install')
        (temporary / 'approved-build.json').write_text(serialized, encoding='utf-8')
        if destination.exists():
            raise SystemExit('fresh non-serving destination required')
        temporary.rename(destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def rollback(approval):
    """Remove only the exact private candidate previously installed by install."""
    manifest = load_manifest()
    root_bin = (ROOT / 'bin').resolve()
    destination = (root_bin / manifest['target']).resolve()
    if not destination.is_relative_to(root_bin):
        raise SystemExit('invalid target destination')
    receipt_path = destination / 'approved-build.json'
    candidate = destination / manifest['build']['artifact']
    if (
        re.fullmatch(r'[0-9a-f]{64}', approval or '') is None
        or not destination.is_dir()
        or not receipt_path.is_file()
        or not candidate.is_file()
        or {path.name for path in destination.iterdir()} != {receipt_path.name, candidate.name}
    ):
        raise SystemExit('installed build identity does not match')
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        valid = (
            receipt.get('schema') == 1
            and receipt.get('approved') is True
            and receipt.get('reviewed_receipt_sha256') == approval
            and receipt.get('candidate_sha256') == sha(candidate)
            and receipt.get('target') == manifest['target']
            and receipt.get('base_commit') == manifest['base_commit']
            and receipt.get('manifest_sha256') == sha(MANIFEST)
            and receipt.get('patch_sha256') == manifest['patch_sha256']
            and receipt.get('build_script_sha256') == sha(Path(__file__))
            and receipt.get('upstream_commits') == manifest['upstream_commits']
            and receipt.get('source') == manifest['source']
            and receipt.get('build') == manifest['build']
            and receipt.get('toolchain') == manifest['toolchain']
            and receipt.get('test_contract') == manifest['test_contract']
            and receipt.get('reference_sha256') == manifest['reference_sha256']
            and _valid_test_evidence(receipt.get('tests'), manifest)
            and receipt.get('compatibility', {}).get('version') == manifest['base_version']
            and receipt.get('compatibility', {}).get('loop_size') == 464
        )
    except (OSError, KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise SystemExit('installed build identity does not match')
    shutil.rmtree(destination)
    return True


HANDLE_TYPES = {'async': 1, 'check': 2, 'fs_event': 3, 'fs_poll': 4, 'handle': 5,
                'idle': 6, 'pipe': 7, 'poll': 8, 'prepare': 9, 'process': 10,
                'stream': 11, 'tcp': 12, 'timer': 13, 'tty': 14, 'udp': 15, 'signal': 16}
REQ_TYPES = {'req': 1, 'connect': 2, 'write': 3, 'shutdown': 4, 'udp_send': 5,
             'fs': 6, 'work': 7, 'getaddrinfo': 8, 'getnameinfo': 9, 'random': 10}


def _dump(dumpbin, option, path):
    value = subprocess.run(
        [str(Path(dumpbin).resolve()), '/nologo', option, str(Path(path).resolve())],
        check=True, capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    return value.stdout


def _abi_direct(path):
    dll = ctypes.WinDLL(str(Path(path).resolve()))
    dll.uv_version_string.restype = ctypes.c_char_p
    dll.uv_loop_size.restype = ctypes.c_size_t
    dll.uv_handle_size.argtypes = [ctypes.c_int]
    dll.uv_handle_size.restype = ctypes.c_size_t
    dll.uv_req_size.argtypes = [ctypes.c_int]
    dll.uv_req_size.restype = ctypes.c_size_t
    return {
        'version': dll.uv_version_string().decode('ascii'),
        'loop_size': dll.uv_loop_size(),
        'handle_sizes': {name: dll.uv_handle_size(value) for name, value in HANDLE_TYPES.items()},
        'req_sizes': {name: dll.uv_req_size(value) for name, value in REQ_TYPES.items()},
    }


def abi_info(path):
    value = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), '_abi', str(Path(path).resolve())],
        check=True, capture_output=True, text=True, encoding='utf-8',
    )
    return json.loads(value.stdout)


def inspect_binary(path, dumpbin):
    try:
        exports_text = _dump(dumpbin, '/exports', path)
        dependencies_text = _dump(dumpbin, '/dependents', path)
        headers_text = _dump(dumpbin, '/headers', path)
        exports = [[int(match.group(1)), match.group(2)] for match in re.finditer(
            r'^\s*(\d+)\s+[0-9A-F]+\s+[0-9A-F]+\s+(\S+)\s*$', exports_text, re.MULTILINE)]
        dependencies = sorted({match.group(1).lower() for match in re.finditer(
            r'^\s*([A-Za-z0-9_.-]+\.dll)\s*$', dependencies_text, re.MULTILINE | re.IGNORECASE)})
        machine = re.search(r'^\s*[0-9A-F]+ machine \(([^)]+)\)', headers_text, re.MULTILINE | re.IGNORECASE)
        abi = abi_info(path)
        if not exports or not dependencies or machine is None or machine.group(1).lower() != 'x64':
            raise ValueError('incomplete PE facts')
        return {
            'version': abi['version'],
            'machine': 'x64',
            'exports': exports,
            'dependencies': dependencies,
            'loop_size': abi['loop_size'],
            'handle_sizes': abi['handle_sizes'],
            'req_sizes': abi['req_sizes'],
        }
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('unable to inspect candidate ABI') from exc


def _test_log(path, expected):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    plan = re.findall(r'^1\.\.(\d+)\s*$', text, re.MULTILINE)
    ids = [int(value) for value in re.findall(r'^(?:ok|not ok) (\d+) - ', text, re.MULTILINE)]
    ok_ids = [int(value) for value in re.findall(r'^ok (\d+) - ', text, re.MULTILINE)]
    skip_names = re.findall(r'^ok \d+ - ([^\r\n#]+?)\s+#\s*SKIP(?:[^\r\n]*)$', text, re.MULTILINE)
    if (
        not set(skip_names).issubset(LOCKED_PLATFORM_SKIPS)
        or len(skip_names) != len(set(skip_names))
        or len(re.findall(r'^ok .*#\s*SKIP', text, re.MULTILINE)) != len(skip_names)
        or re.search(r'^ok .*#\s*TODO', text, re.MULTILINE)
        or plan != [str(expected)]
        or ids != list(range(1, expected + 1))
        or ok_ids != list(range(1, expected + 1))
        or re.search(r'^not ok \d+ - ', text, re.MULTILINE)
    ):
        raise SystemExit('complete libuv tests did not pass')
    return {'tests': expected, 'exit': 0, 'log_sha256': sha(path),
            'skipped': len(skip_names), 'skip_names': sorted(skip_names)}


def validate_build_run(path, candidate):
    """Check a local build record before executing its trusted DLL. This is not a sandbox."""
    try:
        path = Path(path).resolve()
        record = json.loads(path.read_text(encoding='utf-8'))
        manifest = load_manifest()
        candidate = Path(candidate).resolve()
        original, patched = record['source_files'], record['patched_source_files']
        tools = record['tools']
        valid = (
            record.get('schema') == 1
            and record.get('manifest_sha256') == sha(MANIFEST)
            and record.get('patch_sha256') == LOCKED_PATCH_SHA256
            and record.get('build_script_sha256') == sha(Path(__file__))
            and record.get('base_commit') == manifest['base_commit']
            and candidate == path.parent / 'build' / 'uv.dll'
            and record.get('candidate_sha256') == sha(candidate)
            and isinstance(original, dict) and bool(original)
            and set(original) == set(patched)
            and all(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest) for digest in original.values())
            and sorted(name for name in original if original[name] != patched[name]) == sorted(LOCKED_CHANGED_FILES)
            and _tree_facts(path.parent / 'source') == patched
            and set(tools) == {'git', 'cmake', 'cl', 'nmake'}
            and all(Path(tool['path']).is_absolute() and sha(tool['path']) == tool['sha256'] for tool in tools.values())
            and isinstance(record['commands'], list) and bool(record['commands'])
            and all(isinstance(argv, list) and argv and all(isinstance(arg, str) for arg in argv) for argv in record['commands'])
        )
        if not valid:
            raise ValueError('build identity drift')
    except (OSError, TypeError, KeyError, ValueError):
        raise SystemExit('matching local build record is required')
    return record


def verify_existing(candidate, reference, dumpbin, staging, dynamic_log, static_log, test_results, *, build_run=None):
    candidate = Path(candidate).resolve()
    reference = Path(reference).resolve()
    staging = Path(staging).resolve()
    if staging.exists():
        raise SystemExit('use a fresh build staging directory')
    contract = load_manifest()['test_contract']
    tests = {
        name: _test_log(path, spec['tests'])
        for name, path, spec in (
            ('dynamic', dynamic_log, contract['dynamic']),
            ('static', static_log, contract['static']),
        )
    }
    if not isinstance(test_results, dict):
        raise SystemExit('test result receipt is required')
    for name, observed in tests.items():
        supplied = test_results.get(name)
        if supplied != observed:
            raise SystemExit('test result receipt does not match logs')
    build_record = validate_build_run(build_run, candidate)
    if sha(reference) != load_manifest()['reference_sha256']:
        raise SystemExit('reference identity does not match locked Torch DLL')
    candidate_facts = inspect_binary(candidate, dumpbin)
    reference_facts = inspect_binary(reference, dumpbin)
    compare_facts(candidate_facts, reference_facts)
    staged_candidate = staging / 'build' / 'uv.dll'
    staged_candidate.parent.mkdir(parents=True)
    shutil.copyfile(candidate, staged_candidate)
    shutil.copyfile(build_run, staging / 'build-run.json')
    commands = list(build_record['commands'])
    commands.append(['verify-existing', candidate.name, reference.name])
    return create_receipt(
        staging, staged_candidate, reference, candidate_facts, reference_facts, tests,
        commands,
    )


def main(argv):
    if argv[:1] == ['_abi'] and len(argv) == 2:
        print(json.dumps(_abi_direct(argv[1]), sort_keys=True))
        return 0
    if argv[:1] == ['recipe'] and len(argv) == 3:
        print(json.dumps(recipe_commands(argv[1], argv[2]), indent=2))
        return 0
    if argv[:1] == ['build'] and len(argv) == 3:
        candidate, commands = run_recipe(argv[1], argv[2])
        print(json.dumps({'candidate': str(candidate), 'commands': commands}, indent=2))
        return 0
    if argv[:1] == ['install'] and len(argv) == 3:
        install(argv[1], argv[2])
        return 0
    if argv[:1] == ['rollback'] and len(argv) == 2:
        rollback(argv[1])
        return 0
    if argv[:1] == ['verify-existing'] and len(argv) == 9:
        approval = verify_existing(
            argv[1], argv[2], argv[3], argv[4], argv[5], argv[6],
            json.loads(Path(argv[7]).read_text(encoding='utf-8')), build_run=argv[8],
        )
        print(approval)
        return 0
    raise SystemExit(
        'usage: build.py _abi <uv.dll> | recipe <source> <build-dir> | '
        'build <source> <staging> | '
        'verify-existing <candidate> <reference> <dumpbin> <staging> '
        '<dynamic-log> <static-log> <test-results.json> <build-run.json> | '
        'install <staging> <reviewed-receipt-sha256> | rollback <receipt-sha256>'
    )


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
