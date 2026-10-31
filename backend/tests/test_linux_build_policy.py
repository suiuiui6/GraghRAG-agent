import importlib.util
import json
from pathlib import Path
import pytest

@pytest.fixture
def subject(tmp_path, monkeypatch):
    source=Path(__file__).parents[1]/'native/vector_numeric/build.py'
    spec=importlib.util.spec_from_file_location('candidate',source)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    return m

def test_gnu_target_is_supported(subject, monkeypatch):
    monkeypatch.setattr(subject.sys,'platform','linux')
    monkeypatch.setattr(subject.platform,'machine',lambda:'x86_64')
    assert subject.platform_identity()==('x86_64-unknown-linux-gnu','vector-numeric-bridge')

def test_unsupported_arch_rejected(subject, monkeypatch):
    monkeypatch.setattr(subject.platform,'machine',lambda:'arm64')
    with pytest.raises(SystemExit): subject.platform_identity()

@pytest.mark.parametrize('key',['RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER'])
def test_override_rejected(subject,monkeypatch,key):
    monkeypatch.setenv(key,'unsupported')
    with pytest.raises(SystemExit,match='override'): subject.check_overrides()

@pytest.mark.parametrize('change',['schema','target','profile','features','toolchain','files','shape','approved'])
def test_receipt_drift_rejected_before_write(subject,change):
    target,name=subject.platform_identity()
    for file in subject.FILES:
        p=subject.ROOT/file;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(file.encode())
    binary=subject.ROOT/'target'/target/'release'/name
    binary.parent.mkdir(parents=True);binary.write_bytes(b'candidate')
    receipt=dict(schema=1,approved=False,target=target,profile='release',features=['serde_json/std','zmij/default'],toolchain='release: 1.94.0\nhost: '+target+'\n',files={**{f:subject.sha(subject.ROOT/f) for f in subject.FILES},name:subject.sha(binary)})
    approval=subject.sha(binary)
    if change=='shape': receipt=[]
    else: receipt[change]={'schema':2,'target':'wrong','profile':'debug','features':[],'toolchain':'wrong','files':{},'approved':True}[change]
    (subject.ROOT/'build-receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(SystemExit):subject.install(approval)
    assert not (subject.ROOT/'bin').exists()
