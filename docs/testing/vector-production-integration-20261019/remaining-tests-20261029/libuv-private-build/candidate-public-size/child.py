from pathlib import Path
import ctypes,os,hashlib,json
p=Path('D:/graghRAG-agent/.tmp/windows-libuv-cross-mvp-20261029/build-authorized/outputs/libuv.dll')
o=Path('D:/graghRAG-agent/.tmp/windows-uv-candidate-size-probe-20261029');o.mkdir(exist_ok=True)
digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest=='6f91cea90646d077b1bcb6372433ea048bac344e8eeb5e5c8ee4b163f02edf96'
with os.add_dll_directory(str(p.parent)):
    lib=ctypes.CDLL(str(p));lib.uv_version_string.argtypes=[];lib.uv_version_string.restype=ctypes.c_char_p
    lib.uv_loop_size.argtypes=[];lib.uv_loop_size.restype=ctypes.c_size_t
    lib.uv_handle_size.argtypes=[ctypes.c_int];lib.uv_handle_size.restype=ctypes.c_size_t
    lib.uv_req_size.argtypes=[ctypes.c_int];lib.uv_req_size.restype=ctypes.c_size_t
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint];k.GetModuleFileNameW.restype=ctypes.c_uint
    name=ctypes.create_unicode_buffer(32768);assert k.GetModuleFileNameW(lib._handle,name,len(name))
    assert Path(name.value).resolve()==p.resolve()
    handles={label:int(lib.uv_handle_size(code)) for label,code in [('async',1),('check',2),('fs_event',3),('fs_poll',4),('handle',5),('idle',6),('pipe',7),('poll',8),('prepare',9),('process',10),('stream',11),('tcp',12),('timer',13),('tty',14),('udp',15),('signal',16)]}
    requests={label:int(lib.uv_req_size(code)) for label,code in [('req',1),('connect',2),('write',3),('shutdown',4),('udp_send',5),('fs',6),('work',7),('getaddrinfo',8),('getnameinfo',9),('random',10)]}
    r={'scope':'Private candidate public version/size queries only. No networking, handles allocated, callbacks, formal runtime replacement or ABI approval; sizes alone do not prove compatibility.','path':name.value,'sha256':digest,'version':lib.uv_version_string().decode('ascii'),'loop_size':int(lib.uv_loop_size()),'handle_sizes':handles,'request_sizes':requests}
assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
(o/'receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
