import ctypes,hashlib,json,pathlib,torch
# Official ssize_t is signed pointer-sized. End pointers are exclusive; no c_char_p auto conversion.
assert ctypes.sizeof(ctypes.c_ssize_t)==ctypes.sizeof(ctypes.c_void_p)==8
lib=pathlib.Path(torch.__file__).parent/'lib/libtorch_cpu.so'
f=ctypes.CDLL(str(lib)).uv__idna_toascii
f.argtypes=[ctypes.c_void_p]*4;f.restype=ctypes.c_ssize_t
cases=[]
def add(name,data,expected,cap=256):
 assert len(data)<=1024 and 1<=cap<=256
 cases.append((name,data,expected,cap))
for n in [1,254,255,256,257,512]: add('ascii-'+str(n),b'a'*n,b'a'*n)
add('numeric-host-with-suffix',b'0x'+b'0'*246+b'7f000001.example.com',b'0x'+b'0'*246+b'7f000001.example.com')
# Python RFC3492 punycode codec is an independent oracle, not the target function.
label='例子';puny=b'xn--'+label.encode('punycode')
for outlen in [254,255,256,257]:
 prefix=b'a'*(outlen-len(puny)-1)
 add('unicode-output-'+str(outlen),prefix+b'.'+label.encode('utf8'),prefix+b'.'+puny)
for sep in ['。','．','｡']: add('separator-'+hex(ord(sep)),('a'+sep+label).encode('utf8'),b'a.'+puny)
add('utf8-invalid',b'\xff',None)
add('empty',b'',None)
add('small-cap-success',b'a',b'a',2)
add('small-cap-insufficient',b'ab',b'ab',2)
results=[]
for name,data,expected,cap in cases:
 src=ctypes.create_string_buffer(data,len(data)+1)
 storage=(ctypes.c_ubyte*(cap+64))(*([0xa5]*(cap+64)))
 base=ctypes.addressof(storage);dst=base+32
 ret=f(ctypes.addressof(src),ctypes.addressof(src)+len(data),dst,dst+cap)
 allbytes=bytes(storage);canary=allbytes[:32]==b'\xa5'*32 and allbytes[32+cap:]==b'\xa5'*32
 success=expected is not None and len(expected)+1<=cap
 if success: ok=ret==len(expected)+1 and allbytes[32:32+ret]==expected+b'\0'
 else:ok=ret<0
 r={'name':name,'input_bytes':len(data),'expected_output_bytes':None if expected is None else len(expected),'capacity':cap,'return':ret,'expected_success':success,'canary_unchanged':canary,'pass':ok and canary}
 results.append(r)
print(json.dumps({'torch':torch.__version__,'source_library_sha256':hashlib.file_digest(lib.open('rb'),'sha256').hexdigest(),'signature':'ssize_t(char const*,char const*,char*,char*)','network_functions_invoked':False,'cases':results,'all_pass':all(r['pass'] for r in results)},indent=2))
assert all(r['pass'] for r in results)
