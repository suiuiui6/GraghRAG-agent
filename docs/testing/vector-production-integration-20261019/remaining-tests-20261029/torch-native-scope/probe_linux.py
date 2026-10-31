import ctypes,hashlib,json,pathlib,sys,torch
libs=pathlib.Path(torch.__file__).parent/'lib'
r={'torch':torch.__version__,'git':torch.version.git_version,'config':torch.__config__.show(),'libraries':[],'symbol_probes':[]}
for p in sorted(libs.glob('*.so*')):
 r['libraries'].append({'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()})
for name in ['libtorch_cpu.so','libtorch_python.so','libc10.so']:
 h=ctypes.CDLL(str(libs/name))
 v={'library':name,'symbols':{}}
 for symbol in ['uv_version_string','uv_version','uv_getaddrinfo','uv__idna_toascii']:
  try:
   f=getattr(h,symbol)
   if symbol=='uv_version_string': f.restype=ctypes.c_char_p; value=f().decode()
   elif symbol=='uv_version': f.restype=ctypes.c_uint; value=f()
   else: value='export present; not invoked'
   v['symbols'][symbol]=value
  except AttributeError:v['symbols'][symbol]='not exported'
 r['symbol_probes'].append(v)
r['mapped_native_paths']=sorted(set(line.split()[-1] for line in pathlib.Path('/proc/self/maps').read_text().splitlines() if '/' in line and ('.so' in line)))
print(json.dumps(r,indent=2))
