import importlib.metadata as md,json,pathlib,re,sys,collections
norm=lambda s:re.sub(r"[-_.]+","-",s).lower()
expected=json.loads(pathlib.Path("/opt/graphrag-artifacts/expected-packages.json").read_text())
prefix=pathlib.Path("/opt/graphrag-cpu/venv").resolve()
assert pathlib.Path(sys.prefix).resolve()==prefix
cfg=(prefix/"pyvenv.cfg").read_text().lower()
assert "include-system-site-packages = false" in cfg
rows=[{"name":norm(d.metadata["Name"]),"version":d.version,"root":str(pathlib.Path(d.locate_file("")).resolve())} for d in md.distributions()]
counts=collections.Counter(r["name"] for r in rows)
assert all(n==1 for n in counts.values()),dict(counts)
assert all(pathlib.Path(r["root"]).is_relative_to(prefix) for r in rows),rows
actual={r["name"]:r["version"] for r in rows}
assert actual==expected,{"missing":sorted(set(expected)-set(actual)),"extra":sorted(set(actual)-set(expected)),"different":{k:(expected[k],actual.get(k)) for k in expected if actual.get(k)!=expected[k]}}
pathlib.Path("/opt/graphrag-artifacts/installed-packages.json").write_text(json.dumps({"python":sys.version,"executable":sys.executable,"prefix":sys.prefix,"count":len(rows),"distribution_roots":rows,"packages":actual,"duplicates":[],"system_site_packages":False},indent=2))
print("Verified installed158 unique names/versions/roots; no system site packages")
