import compileall,json,pathlib,time
root=pathlib.Path(__file__).resolve().parent
site=root/'.venv/Lib/site-packages'
a=json.loads((root/'precompile-source-hashes.json').read_text()); b=json.loads((root/'postcompile-source-hashes.json').read_text()); assert a==b
before=sum(1 for p in site.rglob('*.pyc'))
start=time.monotonic(); ok=compileall.compile_dir(str(site),quiet=1,workers=1)
receipt={'source_files':len(a),'uv_before_after_source_hashes_equal':a==b,'pyc_before':before,'pyc_after':sum(1 for p in site.rglob('*.pyc')),'compileall_ok':ok,'seconds':time.monotonic()-start}
(root/'compileall-receipt.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt),flush=True)
assert ok
