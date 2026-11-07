"""The private libuv backport must be reproducible from locked source and patch bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest


def test_manifest_locks_v140_and_the_reviewed_patch_bytes():
    root = Path(__file__).resolve().parents[1] / 'native/torch_libuv'
    source = root / 'build.py'
    assert source.is_file(), 'project-owned libuv build recipe is missing'
    spec = importlib.util.spec_from_file_location('torch_libuv_build_subject', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.load_manifest()
    assert manifest['schema'] == 1
    assert manifest['base_version'] == '1.40.0'
    assert manifest['base_commit'] == '4e69e333252693bd82d6338d6124f0416538dbfc'
    assert manifest['upstream_commits'] == [
        'b7466e31e4bee160d82a68fca11b1f61d46debae',
        '0f2d7e784a256b54b2385043438848047bc2a629',
        '3530bcc30350d4a6ccf35d2f7b33e23292b9de70',
        'e0327e1d508b8207c9150b6e582f0adf26213c39',
    ]
    patch = root / manifest['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == manifest['patch_sha256']
    assert manifest['reference_sha256'] == 'fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8'
    assert manifest['changed_files'] == ['src/idna.c', 'test/test-idna.c', 'test/test-list.h']
    assert json.loads((root / 'manifest.json').read_text(encoding='utf-8')) == manifest


@pytest.mark.parametrize('field', ['base_version', 'base_commit', 'target', 'upstream_commits', 'changed_files', 'toolchain', 'patch'])
def test_manifest_rejects_canonical_identity_drift(tmp_path, field):
    module = _load_subject()
    manifest = json.loads(module.MANIFEST.read_text(encoding='utf-8'))
    manifest[field] = 'drifted' if field not in {'upstream_commits', 'changed_files', 'toolchain'} else []
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    module.MANIFEST = manifest_path
    with pytest.raises(SystemExit, match='invalid locked backport manifest'):
        module.load_manifest()


def _load_subject():
    source = Path(__file__).resolve().parents[1] / 'native/torch_libuv/build.py'
    spec = importlib.util.spec_from_file_location('torch_libuv_compat_subject', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _facts():
    return {
        'version': '1.40.0',
        'machine': 'x64',
        'exports': [[1, 'uv_accept'], [2, 'uv_async_init']],
        'dependencies': ['kernel32.dll', 'vcruntime140.dll'],
        'loop_size': 464,
        'handle_sizes': {'async': 224, 'tcp': 320},
        'req_sizes': {'req': 112, 'write': 176},
    }


def _test_results(module, dynamic, static, *, dynamic_exit=0, static_exit=0):
    return {
        'dynamic': {'tests': 402, 'skipped': 0, 'skip_names': [], 'exit': dynamic_exit, 'log_sha256': module.sha(dynamic)},
        'static': {'tests': 405, 'skipped': 0, 'skip_names': [], 'exit': static_exit, 'log_sha256': module.sha(static)},
    }


def test_compatibility_requires_exact_old_abi_facts():
    module = _load_subject()
    summary = module.compare_facts(_facts(), _facts())
    assert summary == {'version': '1.40.0', 'exports': 2, 'loop_size': 464}


import copy


@pytest.mark.parametrize('field,replacement', [
    ('version', '1.53.0'),
    ('machine', 'arm64'),
    ('exports', [[1, 'uv_accept']]),
    ('dependencies', ['kernel32.dll']),
    ('loop_size', 472),
    ('handle_sizes', {'async': 224, 'tcp': 328}),
    ('req_sizes', {'req': 112, 'write': 184}),
])
def test_compatibility_rejects_every_abi_or_loader_drift(field, replacement):
    module = _load_subject()
    candidate = copy.deepcopy(_facts())
    candidate[field] = replacement
    with pytest.raises(SystemExit, match='candidate does not preserve reviewed ABI'):
        module.compare_facts(candidate, _facts())


import shutil


@pytest.fixture
def recipe_copy(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'native/torch_libuv'
    root = tmp_path / 'torch_libuv'
    shutil.copytree(source, root)
    # Execute the production module so coverage measures the real file; redirect only fixture artifacts.
    spec = importlib.util.spec_from_file_location('torch_libuv_receipt_subject', source / 'build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', root)
    monkeypatch.setattr(module, 'MANIFEST', root / 'manifest.json')
    monkeypatch.setattr(module, '__file__', str(root / 'build.py'))
    staging = tmp_path / 'staging'
    candidate = staging / 'build' / 'uv.dll'
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b'candidate-uv-dll')
    reference = tmp_path / 'reference-uv.dll'
    reference.write_bytes(b'original-torch-uv-dll')
    manifest = json.loads(module.MANIFEST.read_text(encoding='utf-8'))
    reference_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    manifest['reference_sha256'] = reference_sha
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(module, 'MANIFEST', manifest_path)
    monkeypatch.setattr(module, 'LOCKED_REFERENCE_SHA256', reference_sha)
    tests = {
        'dynamic': {'tests': 402, 'skipped': 0, 'skip_names': [], 'exit': 0, 'log_sha256': 'a' * 64},
        'static': {'tests': 405, 'skipped': 0, 'skip_names': [], 'exit': 0, 'log_sha256': 'b' * 64},
    }
    _build_record(module, candidate)
    return module, staging, candidate, reference, tests


def test_reviewed_receipt_installs_only_to_fresh_non_serving_staging(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [['cmake', '--build']])
    assert not (module.ROOT / 'bin').exists()
    module.install(staging, approval)
    destination = module.ROOT / 'bin' / module.load_manifest()['target']
    assert (destination / 'uv.dll').read_bytes() == candidate.read_bytes()
    approved = json.loads((destination / 'approved-build.json').read_text(encoding='utf-8'))
    assert approved['approved'] is True
    assert approved['reviewed_receipt_sha256'] == approval
    assert approved['candidate_sha256'] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    with pytest.raises(SystemExit, match='fresh non-serving destination required'):
        module.install(staging, approval)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


@pytest.mark.parametrize('change', ['approval', 'candidate', 'patch', 'manifest', 'script'])
def test_install_rejects_any_reviewed_identity_drift(recipe_copy, change):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    if change == 'approval':
        approval = '0' * 64
    elif change == 'candidate':
        candidate.write_bytes(b'changed')
    elif change == 'patch':
        (module.ROOT / module.load_manifest()['patch']).write_bytes(b'changed')
    elif change == 'manifest':
        module.MANIFEST.write_text('{}', encoding='utf-8')
    else:
        Path(module.__file__).write_text(Path(module.__file__).read_text(encoding='utf-8') + '\n# changed', encoding='utf-8')
    with pytest.raises(SystemExit, match='reviewed build identity does not match'):
        module.install(staging, approval)
    assert not (module.ROOT / 'bin').exists()


def test_binary_inspection_combines_dumpbin_and_runtime_abi(monkeypatch, tmp_path):
    module = _load_subject()
    binary = tmp_path / 'uv.dll'
    binary.write_bytes(b'pe-fixture')
    outputs = {
        '/exports': '    ordinal hint RVA      name\n          1    0 00001000 uv_accept\n          2    1 00001010 uv_async_init\n',
        '/dependents': '  Image has the following dependencies:\n    KERNEL32.dll\n    VCRUNTIME140.dll\n\n  Summary\n',
        '/headers': '             8664 machine (x64)\n',
    }
    monkeypatch.setattr(module, '_dump', lambda dumpbin, option, path: outputs[option])
    monkeypatch.setattr(module, 'abi_info', lambda path: {
        'version': '1.40.0', 'loop_size': 464,
        'handle_sizes': {'async': 224, 'tcp': 320},
        'req_sizes': {'req': 112, 'write': 176},
    })
    assert module.inspect_binary(binary, tmp_path / 'dumpbin.exe') == _facts()


def test_binary_inspection_refuses_incomplete_pe_evidence(monkeypatch, tmp_path):
    module = _load_subject()
    binary = tmp_path / 'uv.dll'
    binary.write_bytes(b'pe-fixture')
    monkeypatch.setattr(module, '_dump', lambda dumpbin, option, path: '')
    monkeypatch.setattr(module, 'abi_info', lambda path: {'version': '1.40.0'})
    with pytest.raises(SystemExit, match='unable to inspect candidate ABI'):
        module.inspect_binary(binary, tmp_path / 'dumpbin.exe')


def test_verify_existing_candidate_counts_full_logs_and_emits_unapproved_receipt(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    staging = tmp_path / 'verified'
    dynamic = tmp_path / 'dynamic.log'
    static = tmp_path / 'static.log'
    dynamic.write_text('1..402\n' + ''.join(f'ok {i} - dynamic_{i}\n' for i in range(1, 403)), encoding='utf-8')
    static.write_text('1..405\n' + ''.join(f'ok {i} - static_{i}\n' for i in range(1, 406)), encoding='utf-8')
    monkeypatch.setattr(module, 'inspect_binary', lambda path, dumpbin: _facts())
    approval = module.verify_existing(candidate, reference, tmp_path / 'dumpbin.exe', staging, dynamic, static, _test_results(module, dynamic, static), build_run=candidate.parent.parent / 'build-run.json')
    receipt = json.loads((staging / 'build-receipt.json').read_text(encoding='utf-8'))
    assert receipt['approved'] is False
    assert receipt['tests'] == {
        'dynamic': {'tests': 402, 'skipped': 0, 'skip_names': [], 'exit': 0, 'log_sha256': module.sha(dynamic)},
        'static': {'tests': 405, 'skipped': 0, 'skip_names': [], 'exit': 0, 'log_sha256': module.sha(static)},
    }
    assert receipt['candidate']['sha256'] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert approval == hashlib.sha256((staging / 'build-receipt.json').read_bytes()).hexdigest()


def test_verify_existing_rejects_incomplete_or_failed_full_logs(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    dynamic = tmp_path / 'dynamic.log'
    static = tmp_path / 'static.log'
    dynamic.write_text('1..402\n' + ''.join(f'ok {i} - dynamic_{i}\n' for i in range(1, 403)) + 'not ok 402 - failed\n', encoding='utf-8')
    static.write_text('1..405\n' + ''.join(f'ok {i} - static_{i}\n' for i in range(1, 406)), encoding='utf-8')
    monkeypatch.setattr(module, 'inspect_binary', lambda path, dumpbin: _facts())
    with pytest.raises(SystemExit, match='complete libuv tests did not pass'):
        module.verify_existing(candidate, reference, tmp_path / 'dumpbin.exe', tmp_path / 'rejected', dynamic, static, _test_results(module, dynamic, static), build_run=candidate.parent.parent / 'build-run.json')
    assert not (tmp_path / 'rejected' / 'build-receipt.json').exists()


def test_verify_existing_receipt_binds_prior_recipe_commands(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    dynamic = tmp_path / 'dynamic.log'
    static = tmp_path / 'static.log'
    dynamic.write_text('1..402\n' + ''.join(f'ok {i} - dynamic_{i}\n' for i in range(1, 403)), encoding='utf-8')
    static.write_text('1..405\n' + ''.join(f'ok {i} - static_{i}\n' for i in range(1, 406)), encoding='utf-8')
    monkeypatch.setattr(module, 'inspect_binary', lambda path, dumpbin: _facts())
    prior = json.loads((candidate.parent.parent / 'build-run.json').read_text())['commands']
    staging = tmp_path / 'verified'
    module.verify_existing(
        candidate,
        reference,
        tmp_path / 'dumpbin.exe',
        staging,
        dynamic,
        static,
        _test_results(module, dynamic, static),
        build_run=candidate.parent.parent / 'build-run.json',
    )
    receipt = json.loads((staging / 'build-receipt.json').read_text(encoding='utf-8'))
    assert receipt['commands'] == prior + [['verify-existing', candidate.name, reference.name]]


def test_manifest_declares_reproducible_source_build_and_test_contract():
    module = _load_subject()
    manifest = module.load_manifest()
    assert manifest['source'] == {
        'kind': 'git-checkout',
        'network': 'no-network-commands',
        'base_commit': manifest['base_commit'],
    }
    assert manifest['build']['generator'] == 'NMake Makefiles'
    assert manifest['build']['configuration'] == 'Release'
    assert manifest['build']['artifact'] == 'uv.dll'
    assert manifest['test_contract'] == {
        'dynamic': {'tests': 402},
        'static': {'tests': 405},
    }


def test_recipe_commands_include_locked_toolchain_and_disconnected_cmake_flags(tmp_path):
    module = _load_subject()
    commands = module.recipe_commands(tmp_path / 'source', tmp_path / 'build')
    assert ['cmake', '--version'] in commands
    assert any(Path(c[0]).stem == 'cl' and c[1:3] == ['/Bv', '/c'] for c in commands)
    assert any(Path(c[0]).stem == 'nmake' and c[1:] == ['/?'] for c in commands)
    configure = next(command for command in commands if command[:2] == ['cmake', '-S'])
    assert '-DFETCHCONTENT_FULLY_DISCONNECTED=ON' in configure
    assert '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF' in configure


def test_install_records_locked_recipe_identity_and_rollback_removes_only_matching_candidate(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [['cmake', '--build']])
    module.install(staging, approval)
    destination = module.ROOT / 'bin' / module.load_manifest()['target']
    installed = json.loads((destination / 'approved-build.json').read_text(encoding='utf-8'))
    assert installed['upstream_commits'] == module.load_manifest()['upstream_commits']
    assert installed['toolchain'] == module.load_manifest()['toolchain']
    assert module.rollback(approval) is True
    assert not destination.exists()


def test_rollback_rejects_a_drifted_or_unapproved_install(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    module.install(staging, approval)
    destination = module.ROOT / 'bin' / module.load_manifest()['target']
    (destination / 'uv.dll').write_bytes(b'drifted')
    with pytest.raises(SystemExit, match='installed build identity does not match'):
        module.rollback(approval)
    assert destination.exists()


def test_recipe_runner_rejects_wrong_or_dirty_source_before_copy(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    calls = []
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        calls.append((args, kwargs))
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            return type('Result', (), {'stdout': 'wrong-commit\n', 'stderr': '', 'returncode': 0})()
        return type('Result', (), {'stdout': ' M dirty.c\n', 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match='source checkout must match locked base commit'):
        module.run_recipe(source, tmp_path / 'staging')
    assert not (tmp_path / 'staging').exists()
    assert len(calls) == 1


def test_recipe_runner_applies_patch_and_builds_only_offline_locked_commands(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    calls = []
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        calls.append((args, kwargs))
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            stdout = module.load_manifest()['base_commit'] + '\n'
        elif args[-3:] == ['status', '--porcelain', '--untracked-files=all']:
            stdout = ''
        elif args[:2] == ['cmake', '--version']:
            stdout = 'cmake version 4.2.3\n'
        elif args[:2] == ['cl', '/Bv']:
            stdout = 'Microsoft C/C++ Optimizing Compiler Version 19.50.35728\nVC Tools 14.50.35717\n'
        elif args[:2] == ['nmake', '/?']:
            stdout = 'Microsoft Program Maintenance Utility Version 14.50.35728\n'
        else:
            stdout = ''
        if '--build' in args:
            artifact = tmp_path / 'staging' / 'build' / 'uv.dll'
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b'candidate')
        return type('Result', (), {'stdout': stdout, 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    candidate, commands = module.run_recipe(source, tmp_path / 'staging')
    assert candidate.read_bytes() == b'candidate'
    assert commands[0][0:4] == ['git', '-C', str(source.resolve()), 'rev-parse']
    assert any(Path(command[0]).stem == 'git' and command[1:4] == ['-C', str((tmp_path / 'staging' / 'source').resolve()), 'apply'] for command in commands)
    assert any(
        'FETCHCONTENT_FULLY_DISCONNECTED=ON' in part
        for command in commands
        for part in command
    )
    assert any(Path(c[0]).stem == 'cl' and c[1:3] == ['/Bv', '/c'] for c in commands)
    assert any(Path(c[0]).stem == 'nmake' and c[1:] == ['/?'] for c in commands)
    assert not (tmp_path / 'staging' / 'build-receipt.json').exists()


def test_recipe_runner_rejects_toolchain_drift_and_preserves_diagnostics(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            stdout = module.load_manifest()['base_commit'] + '\n'
        elif args[-3:] == ['status', '--porcelain', '--untracked-files=all']:
            stdout = ''
        elif args[:2] == ['cmake', '--version']:
            stdout = 'cmake version 4.2.3\n'
        elif args[:2] == ['cl', '/Bv']:
            stdout = 'Microsoft C/C++ Optimizing Compiler Version 19.49.00000\n'
        else:
            stdout = ''
        return type('Result', (), {'stdout': stdout, 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match='unexpected MSVC identity'):
        module.run_recipe(source, tmp_path / 'staging')
    assert (tmp_path / 'staging').is_dir()
    assert not (tmp_path / 'staging' / 'build-run.json').exists()



def test_cli_install_and_rollback_use_reviewed_receipt(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    assert module.main(['install', str(staging), approval]) == 0
    destination = module.ROOT / 'bin' / module.LOCKED_TARGET
    assert (destination / 'uv.dll').read_bytes() == candidate.read_bytes()
    assert module.main(['rollback', approval]) == 0
    assert not destination.exists()


def test_cli_verify_existing_reads_test_results(recipe_copy, monkeypatch, tmp_path, capsys):
    module, _, candidate, reference, _ = recipe_copy
    dynamic, static = tmp_path / 'dynamic.log', tmp_path / 'static.log'
    for path, count in ((dynamic, 402), (static, 405)):
        path.write_text(f'1..{count}\n' + ''.join(f'ok {i} - case_{i}\n' for i in range(1, count + 1)))
    results = tmp_path / 'results.json'
    results.write_text(json.dumps(_test_results(module, dynamic, static)))
    monkeypatch.setattr(module, 'inspect_binary', lambda *args: _facts())
    staging = tmp_path / 'verified-cli'
    assert module.main(['verify-existing', str(candidate), str(reference), 'dumpbin', str(staging),
                        str(dynamic), str(static), str(results), str(candidate.parent.parent / 'build-run.json')]) == 0
    assert capsys.readouterr().out.strip() == module.sha(staging / 'build-receipt.json')


def test_manifest_rejects_patch_and_manifest_drifting_together(recipe_copy):
    module, *_ = recipe_copy
    patch = module.ROOT / 'patches/idna-backport.patch'
    patch.write_bytes(patch.read_bytes() + b'\n')
    value = json.loads(module.MANIFEST.read_text())
    value['patch_sha256'] = module.sha(patch)
    module.MANIFEST.write_text(json.dumps(value))
    with pytest.raises(SystemExit, match='invalid locked backport manifest'):
        module.load_manifest()


@pytest.mark.parametrize('dynamic_exit,static_exit', [(1, 0), (0, 1)])
def test_verify_rejects_nonzero_actual_test_exit_before_dll_load(recipe_copy, monkeypatch, tmp_path, dynamic_exit, static_exit):
    module, _, candidate, reference, _ = recipe_copy
    dynamic, static = tmp_path / 'dynamic.log', tmp_path / 'static.log'
    for path, count in ((dynamic, 402), (static, 405)):
        path.write_text(f'1..{count}\n' + ''.join(f'ok {i} - case_{i}\n' for i in range(1, count + 1)))
    monkeypatch.setattr(module, 'inspect_binary', lambda *args: pytest.fail('unapproved DLL loaded'))
    with pytest.raises(SystemExit, match='test result receipt does not match logs'):
        module.verify_existing(candidate, reference, 'dumpbin', tmp_path / 'rejected', dynamic, static,
            _test_results(module, dynamic, static, dynamic_exit=dynamic_exit, static_exit=static_exit))


def test_tap_duplicate_ids_cannot_replace_a_missing_case(tmp_path):
    module = _load_subject()
    path = tmp_path / 'tap.log'
    path.write_text('1..402\n' + ''.join(f'ok {i if i != 402 else 401} - case\n' for i in range(1, 403)))
    with pytest.raises(SystemExit, match='complete libuv tests did not pass'):
        module._test_log(path, 402)


def test_recipe_command_includes_stderr_for_real_msvc_version(monkeypatch, tmp_path):
    module = _load_subject()
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: type('Result', (), {
        'stdout': '', 'stderr': 'Microsoft Compiler 19.50.35728', 'returncode': 0})())
    assert '19.50.35728' in module._run_recipe_command(['cl', '/Bv'], tmp_path, [])



def _fake_tools(module, monkeypatch, tmp_path):
    tools = tmp_path / 'tools' / module.LOCKED_TOOLCHAIN['vctools']
    tools.mkdir(parents=True, exist_ok=True)
    for name in ('git', 'cmake', 'cl', 'nmake'):
        (tools / (name + '.exe')).write_bytes(name.encode())
    monkeypatch.setattr(module.shutil, 'which', lambda name: str(tools / (Path(name).stem + '.exe')))


def _build_record(module, candidate):
    staging = candidate.parent.parent
    source = staging / 'source'
    for name in module.LOCKED_CHANGED_FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'patched-source')
    facts = module._tree_facts(source)
    original = {name: 'a' * 64 for name in facts}
    tool = staging / 'tool.exe'
    tool.write_bytes(b'tool-fixture')
    record = {'schema': 1, 'manifest_sha256': module.sha(module.MANIFEST),
        'patch_sha256': module.LOCKED_PATCH_SHA256, 'build_script_sha256': module.sha(module.__file__),
        'base_commit': module.LOCKED_BASE_COMMIT, 'source_files': original,
        'patched_source_files': facts, 'candidate_sha256': module.sha(candidate),
        'tools': {name: {'path': str(tool), 'sha256': module.sha(tool)} for name in ('git', 'cmake', 'cl', 'nmake')},
        'commands': [['git', 'apply'], ['cmake', '--build']]}
    path = staging / 'build-run.json'
    path.write_text(json.dumps(record))
    return path


def test_verify_requires_build_record_before_loading_any_dll(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    dynamic, static = tmp_path / 'dynamic.log', tmp_path / 'static.log'
    for path, count in ((dynamic, 402), (static, 405)):
        path.write_text(f'1..{count}\n' + ''.join(f'ok {i} - case_{i}\n' for i in range(1, count + 1)))
    monkeypatch.setattr(module, 'inspect_binary', lambda *a: pytest.fail('unapproved DLL loaded'))
    with pytest.raises(SystemExit, match='matching local build record is required'):
        module.verify_existing(candidate, reference, 'dumpbin', tmp_path / 'rejected', dynamic, static,
            _test_results(module, dynamic, static))


@pytest.mark.parametrize('change', ['candidate', 'script', 'source', 'tool'])
def test_verify_rejects_build_provenance_drift_before_dll_load(recipe_copy, monkeypatch, tmp_path, change):
    module, staging, candidate, reference, _ = recipe_copy
    dynamic, static = tmp_path / 'dynamic.log', tmp_path / 'static.log'
    for path, count in ((dynamic, 402), (static, 405)):
        path.write_text(f'1..{count}\n' + ''.join(f'ok {i} - case_{i}\n' for i in range(1, count + 1)))
    record = staging / 'build-run.json'
    if change == 'candidate':
        candidate.write_bytes(b'drifted')
    elif change == 'script':
        data = json.loads(record.read_text())
        data['build_script_sha256'] = '0' * 64
        record.write_text(json.dumps(data))
    elif change == 'source':
        (staging / 'source/src/idna.c').write_bytes(b'drifted')
    else:
        (staging / 'tool.exe').write_bytes(b'drifted')
    monkeypatch.setattr(module, 'inspect_binary', lambda *a: pytest.fail('unapproved DLL loaded'))
    with pytest.raises(SystemExit, match='matching local build record is required'):
        module.verify_existing(candidate, reference, 'dumpbin', tmp_path / 'rejected', dynamic, static,
            _test_results(module, dynamic, static), build_run=record)



def test_tap_reports_supported_windows_skips_separately(tmp_path):
    module = _load_subject()
    path = tmp_path / 'tap.log'
    path.write_text('1..402\n' + 'ok 1 - eintr_handling # SKIP upstream platform condition\n' +
        ''.join(f'ok {i} - case_{i}\n' for i in range(2, 403)))
    result = module._test_log(path, 402)
    assert result['skipped'] == 1
    assert result['skip_names'] == ['eintr_handling']


def test_tap_rejects_skipping_the_security_regression(tmp_path):
    module = _load_subject()
    path = tmp_path / 'tap.log'
    path.write_text('1..402\n' + 'ok 1 - utf8_decode1_overrun # SKIP\n' +
        ''.join(f'ok {i} - case_{i}\n' for i in range(2, 403)))
    with pytest.raises(SystemExit, match='complete libuv tests did not pass'):
        module._test_log(path, 402)

def _tap_logs(tmp_path, dynamic=402, static=405):
    dynamic_path = tmp_path / 'dynamic.log'
    static_path = tmp_path / 'static.log'
    dynamic_path.write_text(f'1..{dynamic}\n' + ''.join(f'ok {i} - dynamic_{i}\n' for i in range(1, dynamic + 1)))
    static_path.write_text(f'1..{static}\n' + ''.join(f'ok {i} - static_{i}\n' for i in range(1, static + 1)))
    return dynamic_path, static_path


def test_recipe_rejects_forbidden_build_environment_override(monkeypatch, tmp_path):
    module = _load_subject()
    monkeypatch.setenv('VCPKG_ROOT', 'forbidden')
    with pytest.raises(SystemExit, match='unsupported build environment override'):
        module.run_recipe(tmp_path / 'source', tmp_path / 'staging')


def test_tree_facts_ignores_git_metadata(tmp_path):
    module = _load_subject()
    source = tmp_path / 'source'
    (source / '.git').mkdir(parents=True)
    (source / '.git/HEAD').write_text('ref: refs/heads/main')
    (source / 'src.c').write_text('int main(void) { return 0; }')
    facts = module._tree_facts(source)
    assert facts == {'src.c': module.sha(source / 'src.c')}


def test_recipe_rejects_missing_source_or_occupied_staging(tmp_path):
    module = _load_subject()
    with pytest.raises(SystemExit, match='source checkout is missing'):
        module.run_recipe(tmp_path / 'missing', tmp_path / 'staging')
    source = tmp_path / 'source'
    source.mkdir()
    staging = tmp_path / 'occupied'
    staging.mkdir()
    with pytest.raises(SystemExit, match='fresh build staging directory outside source'):
        module.run_recipe(source, staging)
    with pytest.raises(SystemExit, match='fresh build staging directory outside source'):
        module.run_recipe(source, source / 'nested')


def test_recipe_rejects_dirty_checkout_before_copy(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            return type('Result', (), {'stdout': module.load_manifest()['base_commit'] + '\n', 'stderr': '', 'returncode': 0})()
        return type('Result', (), {'stdout': ' M dirty.c\n', 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match='source checkout must be clean'):
        module.run_recipe(source, tmp_path / 'staging')


def test_recipe_rejects_missing_local_tool(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    monkeypatch.setattr(module.shutil, 'which', lambda name: None)
    def run(args, **kwargs):
        args = [Path(args[0]).stem] + args[1:]
        stdout = module.load_manifest()['base_commit'] + '\n' if args[-2:] == ['rev-parse', 'HEAD'] else ''
        return type('Result', (), {'stdout': stdout, 'stderr': '', 'returncode': 0})()
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match='required local build tool is missing'):
        module.run_recipe(source, tmp_path / 'staging')


def test_recipe_rejects_source_mutation_during_copy(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'src.c').write_text('source')
    _fake_tools(module, monkeypatch, tmp_path)
    monkeypatch.setattr(module.subprocess, 'run', lambda args, **kwargs: type('Result', (), {
        'stdout': module.load_manifest()['base_commit'] + '\n' if str(args[-1]) == 'HEAD' else '',
        'stderr': '', 'returncode': 0})())
    monkeypatch.setattr(module, '_tree_facts', lambda path: {'src.c': 'a' * 64} if Path(path) == source else {'src.c': 'b' * 64})
    with pytest.raises(SystemExit, match='source changed during copy'):
        module.run_recipe(source, tmp_path / 'staging')
    assert not (tmp_path / 'staging' / 'build-run.json').exists()


@pytest.mark.parametrize('tool, output, message', [
    ('cmake', 'cmake version 0.0.0\n', 'unexpected CMake identity'),
    ('cmake', 'cmake version 4.2.3\n', 'unexpected NMake identity'),
])
def test_recipe_rejects_toolchain_identity_drift(tmp_path, monkeypatch, tool, output, message):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            stdout = module.load_manifest()['base_commit'] + '\n'
        elif args[-3:] == ['status', '--porcelain', '--untracked-files=all']:
            stdout = ''
        elif args[:2] == ['cmake', '--version']:
            stdout = output
        elif args[:2] == ['cl', '/Bv']:
            stdout = 'Microsoft C/C++ Optimizing Compiler Version 19.50.35728\nVC Tools 14.50.35717\n'
        elif args[:2] == ['nmake', '/?']:
            stdout = 'Microsoft Program Maintenance Utility Version 14.49.00000\n'
        else:
            stdout = ''
        return type('Result', (), {'stdout': stdout, 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match=message):
        module.run_recipe(source, tmp_path / 'staging')


def test_recipe_requires_exactly_one_built_artifact(tmp_path, monkeypatch):
    module = _load_subject()
    source = tmp_path / 'source'
    source.mkdir()
    _fake_tools(module, monkeypatch, tmp_path)

    def run(args, **kwargs):
        args = [Path(args[0]).stem] + args[1:]
        if args[-2:] == ['rev-parse', 'HEAD']:
            stdout = module.load_manifest()['base_commit'] + '\n'
        elif args[-3:] == ['status', '--porcelain', '--untracked-files=all']:
            stdout = ''
        elif args[:2] == ['cmake', '--version']:
            stdout = 'cmake version 4.2.3\n'
        elif args[:2] == ['cl', '/Bv']:
            stdout = 'Microsoft C/C++ Optimizing Compiler Version 19.50.35728\nVC Tools 14.50.35717\n'
        elif args[:2] == ['nmake', '/?']:
            stdout = 'Microsoft Program Maintenance Utility Version 14.50.35728\n'
        else:
            stdout = ''
        return type('Result', (), {'stdout': stdout, 'stderr': '', 'returncode': 0})()

    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(SystemExit, match='expected exactly one built libuv artifact'):
        module.run_recipe(source, tmp_path / 'staging')


def test_test_evidence_rejects_wrong_contract_shape():
    module = _load_subject()
    manifest = module.load_manifest()
    assert module._valid_test_evidence([], manifest) is False
    assert module._valid_test_evidence({'dynamic': {}}, manifest) is False


def test_create_receipt_rejects_existing_receipt_and_outside_candidate(recipe_copy, tmp_path):
    module, staging, candidate, reference, tests = recipe_copy
    (staging / 'build-receipt.json').write_text('{}')
    with pytest.raises(SystemExit, match='use a fresh build staging directory'):
        module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    (staging / 'build-receipt.json').unlink()
    outside = tmp_path / 'outside.dll'
    outside.write_bytes(b'outside')
    with pytest.raises(SystemExit, match='use a fresh build staging directory'):
        module.create_receipt(staging, outside, reference, _facts(), _facts(), tests, [])


def test_create_receipt_rejects_reference_drift(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    reference.write_bytes(b'changed-reference')
    with pytest.raises(SystemExit, match='reference identity does not match locked Torch DLL'):
        module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])


def test_install_rejects_existing_temporary_destination(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    target = module.load_manifest()['target']
    temporary = module.ROOT / 'bin' / ('.' + target + '.install-' + approval)
    temporary.mkdir(parents=True)
    with pytest.raises(SystemExit, match='fresh non-serving destination required'):
        module.install(staging, approval)
    assert temporary.exists()


def test_install_cleans_up_when_candidate_changes_during_copy(recipe_copy, monkeypatch):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    monkeypatch.setattr(module.shutil, 'copyfile', lambda source, target: Path(target).write_bytes(b'changed-during-install'))
    with pytest.raises(SystemExit, match='candidate changed during install'):
        module.install(staging, approval)
    assert not (module.ROOT / 'bin' / module.load_manifest()['target']).exists()


def test_rollback_rejects_malformed_approved_receipt(recipe_copy):
    module, staging, candidate, reference, tests = recipe_copy
    approval = module.create_receipt(staging, candidate, reference, _facts(), _facts(), tests, [])
    module.install(staging, approval)
    destination = module.ROOT / 'bin' / module.load_manifest()['target']
    (destination / 'approved-build.json').write_text('{}')
    with pytest.raises(SystemExit, match='installed build identity does not match'):
        module.rollback(approval)


def test_dump_abi_info_and_direct_abi_branches(monkeypatch, tmp_path):
    module = _load_subject()
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: type('Result', (), {
        'stdout': 'dump-output\n', 'stderr': '', 'returncode': 0})())
    assert module._dump(tmp_path / 'dumpbin.exe', '/exports', tmp_path / 'uv.dll') == 'dump-output\n'
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: type('Result', (), {
        'stdout': '{"version": "1.40.0", "loop_size": 464, "handle_sizes": {}, "req_sizes": {}}',
        'stderr': '', 'returncode': 0})())
    assert module.abi_info(tmp_path / 'uv.dll')['loop_size'] == 464

    class FakeFn:
        restype = None
        argtypes = None
        def __init__(self, value): self.value = value
        def __call__(self, *args): return self.value

    class FakeDll:
        def __init__(self, path):
            self.uv_version_string = FakeFn(b'1.40.0')
            self.uv_loop_size = FakeFn(464)
            self.uv_handle_size = FakeFn(224)
            self.uv_req_size = FakeFn(112)

    monkeypatch.setattr(module.ctypes, 'WinDLL', FakeDll)
    assert module._abi_direct('uv.dll')['handle_sizes']['async'] == 224


def test_cli_dispatch_and_usage(monkeypatch, capsys):
    module = _load_subject()
    monkeypatch.setattr(module, '_abi_direct', lambda path: {'version': '1.40.0'})
    assert module.main(['_abi', 'uv.dll']) == 0
    monkeypatch.setattr(module, 'recipe_commands', lambda source, staging: [['cmake', '--version']])
    assert module.main(['recipe', 'source', 'staging']) == 0
    monkeypatch.setattr(module, 'run_recipe', lambda source, staging: (Path('candidate'), []))
    assert module.main(['build', 'source', 'staging']) == 0
    with pytest.raises(SystemExit, match='usage:'):
        module.main([])
    assert '1.40.0' in capsys.readouterr().out


def test_verify_existing_rejects_occupied_staging_and_bad_test_results(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    dynamic, static = _tap_logs(tmp_path)
    occupied = tmp_path / 'occupied'
    occupied.mkdir()
    with pytest.raises(SystemExit, match='use a fresh build staging directory'):
        module.verify_existing(candidate, reference, 'dumpbin', occupied, dynamic, static,
            _test_results(module, dynamic, static), build_run=candidate.parent.parent / 'build-run.json')
    with pytest.raises(SystemExit, match='test result receipt is required'):
        module.verify_existing(candidate, reference, 'dumpbin', tmp_path / 'rejected', dynamic, static,
            [], build_run=candidate.parent.parent / 'build-run.json')


def test_verify_existing_rejects_reference_drift_before_dll_load(recipe_copy, monkeypatch, tmp_path):
    module, _, candidate, reference, _ = recipe_copy
    dynamic, static = _tap_logs(tmp_path)
    reference.write_bytes(b'changed-reference')
    monkeypatch.setattr(module, 'inspect_binary', lambda *a: pytest.fail('unapproved DLL loaded'))
    with pytest.raises(SystemExit, match='reference identity does not match locked Torch DLL'):
        module.verify_existing(candidate, reference, 'dumpbin', tmp_path / 'rejected', dynamic, static,
            _test_results(module, dynamic, static), build_run=candidate.parent.parent / 'build-run.json')
