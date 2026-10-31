import json,pathlib,subprocess,sys,threading
import filelock
from filelock import FileLock,Timeout
root=pathlib.Path(__file__).parent
path=root/'independent-contract.lock'
assert FileLock is filelock.WindowsFileLock
lock=FileLock(path,thread_local=False)
lock.acquire(timeout=0);lock.acquire(timeout=0)
assert lock.lock_counter==2
lock.release();assert lock.is_locked
code="from filelock import FileLock,Timeout;import sys;\ntry:\n with FileLock(sys.argv[1]).acquire(timeout=0):print('acquired',flush=True)\nexcept Timeout:print('timeout',flush=True);sys.exit(7)"
p=subprocess.run([sys.executable,'-B','-c',code,str(path)],text=True,capture_output=True,timeout=10)
assert p.returncode==7 and p.stdout.strip()=='timeout',(p.returncode,p.stdout,p.stderr)
t=threading.Thread(target=lock.release);t.start();t.join(5)
assert not t.is_alive() and not lock.is_locked
p=subprocess.run([sys.executable,'-B','-c',code,str(path)],text=True,capture_output=True,timeout=10)
assert p.returncode==0 and p.stdout.strip()=='acquired'
hold="from filelock import FileLock;import sys;lock=FileLock(sys.argv[1]);lock.acquire();print('held',flush=True);sys.stdin.read()"
child=subprocess.Popen([sys.executable,'-B','-c',hold,str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    assert child.stdout.readline().strip()=='held'
    try:
        FileLock(path).acquire(timeout=0)
        raise AssertionError('live owner not excluded')
    except Timeout:pass
finally:
    child.kill();child.communicate(timeout=10)
with FileLock(path).acquire(timeout=1):pass
result={'filelock':filelock.__version__,'module':filelock.__file__,'backend':FileLock.__name__,'reentrant_counter':True,'timeout_caught':True,'cross_process_exclusion':True,'cross_thread_release':True,'reacquisition':True,'killed_owner_recovery':True}
(root/'contract-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
