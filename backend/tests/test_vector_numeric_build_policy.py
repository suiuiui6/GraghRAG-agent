"""The native installer must bind approval to both binary and source bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def native_build(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'native/vector_numeric/build.py'
    spec = importlib.util.spec_from_file_location('numeric_build_policy_subject', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    monkeypatch.setattr(module.platform, 'machine', lambda: 'AMD64')
    for name in module.FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('locked-' + name).encode())
    binary = tmp_path / 'target' / module.TARGET / 'release' / module.NAME
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b'local-test-binary-not-executable')
    for crate, enabled in module.COMPILED.items():
        fingerprint = tmp_path / 'target' / module.TARGET / 'release' / '.fingerprint' / (crate+'-fixed') / ('lib-'+crate+'.json')
        fingerprint.parent.mkdir(parents=True)
        fingerprint.write_text(json.dumps({'features': json.dumps(enabled)}))
    return module


def compiler_calls(module, monkeypatch, *, compiler=None, features='serde_json std\nzmij default\n'):
    calls = []
    if compiler is None:
        compiler = 'release: 1.94.0\nhost: ' + module.TARGET + '\n'
    def run(args, **kwargs):
        calls.append((args, kwargs))
        output = compiler if args[:4] == ['rustup', 'run', '1.94.0', 'rustc'] else features
        if args == ['rustup', 'run', '1.94.0', 'cargo', '--version']: output='cargo 1.94.0 (fixed)'
        if 'metadata' in args:
            output=json.dumps({'packages':[{'id':n,'name':n} for n in module.GRAPH],
                               'resolve':{'nodes':[{'id':n,'features':f} for n,f in module.GRAPH.items()]}})
        return SimpleNamespace(stdout=output,stderr='',returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', run)
    return calls


def test_build_creates_unapproved_receipt_without_installing(native_build, monkeypatch):
    module = native_build
    calls = compiler_calls(module, monkeypatch)
    digest = module.build()
    receipt = json.loads((module.ROOT / 'build-receipt.json').read_text())
    assert receipt['approved'] is False
    assert receipt['files'][module.NAME] == digest
    assert receipt['files'] == {**{name: module.sha(module.ROOT / name) for name in module.FILES},
                                module.NAME: module.sha(module.ROOT / 'target' / module.TARGET / 'release' / module.NAME)}
    assert calls[0][0] == ['rustup', 'run', '1.94.0', 'rustc', '--version', '--verbose']
    assert any(argv == ['rustup', 'run', '1.94.0', 'cargo', 'build', '--offline', '--locked', '--release', '--target', module.TARGET, '--verbose'] for argv,_ in calls)
    assert all(options['check'] is True and options['cwd'] == module.ROOT for _, options in calls)
    assert not (module.ROOT / 'bin').exists()


def test_unapproved_platform_cannot_start_compiler(native_build, monkeypatch):
    module = native_build
    calls = compiler_calls(module, monkeypatch)
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    with pytest.raises(SystemExit, match='unsupported platform'):
        module.build()
    assert calls == []
    assert not (module.ROOT / 'build-receipt.json').exists()


@pytest.mark.parametrize('compiler', ['release: 1.93.0\nhost: x86_64-pc-windows-msvc\n',
                                    'release: 1.94.0\nhost: unapproved-target\n'])
def test_compiler_mismatch_produces_no_receipt(native_build, monkeypatch, compiler):
    compiler_calls(native_build, monkeypatch, compiler=compiler)
    with pytest.raises(SystemExit, match='unexpected compiler identity'):
        native_build.build()
    assert not (native_build.ROOT / 'build-receipt.json').exists()


@pytest.mark.parametrize('feature', ['float_roundtrip', 'arbitrary_precision'])
def test_parser_changing_feature_cannot_be_approved(native_build, monkeypatch, feature):
    compiler_calls(native_build, monkeypatch, features=feature)
    with pytest.raises(SystemExit, match='unsupported parser features'):
        native_build.build()
    assert not (native_build.ROOT / 'build-receipt.json').exists()


@pytest.mark.parametrize('change', ['approval', 'binary', 'source'])
def test_install_rejects_any_reviewed_identity_drift(native_build, monkeypatch, change):
    module = native_build
    compiler_calls(module, monkeypatch)
    approval = module.build()
    if change == 'approval':
        approval = '0' * 64
    elif change == 'binary':
        (module.ROOT / 'target' / module.TARGET / 'release' / module.NAME).write_bytes(b'changed binary')
    else:
        (module.ROOT / 'src/main.rs').write_bytes(b'changed source')
    with pytest.raises(SystemExit, match='reviewed build identity does not match'):
        module.install(approval)
    assert not (module.ROOT / 'bin').exists()
    assert json.loads((module.ROOT / 'build-receipt.json').read_text())['approved'] is False


def test_install_copies_exact_approved_binary_with_receipt(native_build, monkeypatch):
    module = native_build
    compiler_calls(module, monkeypatch)
    approval = module.build()
    module.install(approval)
    destination = module.ROOT / 'bin' / module.TARGET
    assert hashlib.sha256((destination / module.NAME).read_bytes()).hexdigest() == approval
    receipt = json.loads((destination / 'approved-build.json').read_text())
    assert receipt['approved'] is True
    assert receipt['files'][module.NAME] == approval
    assert receipt['target'] == module.TARGET


@pytest.mark.parametrize('change',['cargo','graph','compiled','source','compiler_failure'])
def test_build_drift_or_failure_never_emits_receipt(native_build,monkeypatch,change):
    module=native_build
    compiler_calls(module,monkeypatch)
    original=module.subprocess.run
    def changed(args,**kwargs):
        value=original(args,**kwargs)
        if change=='cargo' and args[-1]=='--version':value.stdout='cargo 1.93.0 old'
        if change=='graph' and 'metadata' in args:
            data=json.loads(value.stdout);data['resolve']['nodes'][0]['features']=[];value.stdout=json.dumps(data)
        if 'build' in args:
            if change=='source':(module.ROOT/'src/main.rs').write_bytes(b'drift')
            if change=='compiled':
                path=next((module.ROOT/'target'/module.TARGET/'release/.fingerprint').glob('zmij-*/lib-zmij.json'))
                path.write_text(json.dumps({'features':'["unsupported"]'}))
            if change=='compiler_failure':raise module.subprocess.CalledProcessError(101,args,output='',stderr='offline dependency missing')
        return value
    monkeypatch.setattr(module.subprocess,'run',changed)
    with pytest.raises((SystemExit,module.subprocess.CalledProcessError)):module.build()
    assert not (module.ROOT/'build-receipt.json').exists()
    assert not (module.ROOT/'bin').exists()


def test_existing_installed_package_is_never_overwritten(native_build,monkeypatch):
    module=native_build;compiler_calls(module,monkeypatch)
    approval=module.build();module.install(approval)
    destination=module.ROOT/'bin'/module.TARGET
    before={p.name:p.read_bytes() for p in destination.iterdir()}
    with pytest.raises(SystemExit,match='fresh non-serving'):module.install(approval)
    assert {p.name:p.read_bytes() for p in destination.iterdir()}==before


def test_every_rust_command_requires_installed_toolchain(native_build, monkeypatch):
    calls = compiler_calls(native_build, monkeypatch)
    native_build.build()
    assert len(calls) == 5
    for argv, _ in calls:
        assert argv[:3] == ['rustup', 'run', '1.94.0'], argv
        assert argv[3] in ('rustc', 'cargo'), argv
        assert '--install' not in argv
        assert not any(part.startswith('+') for part in argv)
        if argv[3] == 'cargo' and any(command in argv for command in ('tree', 'metadata', 'build')):
            assert '--offline' in argv and '--locked' in argv
