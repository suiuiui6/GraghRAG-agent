import importlib.util,json,pathlib
import pytest

def test_oversize_valid_identity_rejected_before_destination(tmp_path):
 p=pathlib.Path(__file__).parents[1]/'native/vector_numeric/build.py'
 spec=importlib.util.spec_from_file_location('independent_candidate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=tmp_path
 target,name=m.platform_identity()
 for f in m.FILES:
  p=tmp_path/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f.encode())
 binary=tmp_path/'target'/target/'release'/name;binary.parent.mkdir(parents=True);binary.write_bytes(b'independent valid bytes')
 approval=m.sha(binary)
 receipt=dict(schema=1,approved=False,target=target,profile='release',features=m.LABELS,toolchain='release: 1.94.0\nhost: '+target+'\n'+'x'*8200,files={**{f:m.sha(tmp_path/f) for f in m.FILES},name:approval})
 (tmp_path/'build-receipt.json').write_text(json.dumps(receipt))
 with pytest.raises(SystemExit,match='manifest too large'):m.install(approval)
 assert not (tmp_path/'bin').exists()
