import json,pathlib,sqlite3,ssl,sys,subprocess,pyexpat
import numpy as np,msgpack,vector_runtime as vr
R=pathlib.Path(__file__).resolve().parent;p=R/'normal.sqlite';b=R/'backup.sqlite'
r={'python':sys.version,'sqlite':sqlite3.sqlite_version,'openssl':ssl.OPENSSL_VERSION,'expat':pyexpat.EXPAT_VERSION,'numpy':np.__version__,'msgpack':msgpack.__version__,'runtime':vr.probe_runtime()}
assert sys.version_info[:3]==(3,12,16) and sqlite3.sqlite_version=='3.54.0'
parser=pyexpat.ParserCreate();text=[];parser.CharacterDataHandler=text.append;parser.Parse('<root>normal text</root>',True);assert ''.join(text)=='normal text'
ssl.create_default_context();a=np.array([1.,2.,3.],dtype=np.float64);payload=a.tobytes()
with vr.connect(p) as c:
 assert c.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
 for option,enabled in vr.HARDENING_OPTIONS:assert c.getconfig(option)==enabled
 c.execute('create table normal(id integer primary key, payload blob)');c.execute('insert into normal values (?,?)',(1,payload));c.commit();c.execute('insert into normal values (?,?)',(2,payload));c.rollback();assert c.execute('select count(*) from normal').fetchone()[0]==1
 got=np.frombuffer(c.execute('select payload from normal where id=?',(1,)).fetchone()[0],dtype=np.float64);assert np.array_equal(a,got);assert abs(float(np.dot(a,got)/(np.linalg.norm(a)*np.linalg.norm(got)))-1)<1e-12
 with vr.connect(b) as dest:c.backup(dest)
with vr.connect(b,ro=True) as c:assert c.execute('select payload from normal').fetchone()[0]==payload
child=subprocess.run([sys.executable,'-B','-c','import sys,vector_runtime as v; c=v.connect(sys.argv[1],ro=True); assert c.execute("select count(*) from normal").fetchone()[0]==1; c.close();print("reopen_ok")',str(p)],capture_output=True,text=True,timeout=35);assert child.returncode==0,child.stderr
obj={'normal':[1,'text',True],'blob':b'abc'};assert msgpack.unpackb(msgpack.packb(obj,use_bin_type=True),raw=False)==obj
r.update(wal=True,rollback=True,blob=True,backup=True,child={'exit':child.returncode,'stdout':child.stdout},cosine=True,expat_parse=True,msgpack_roundtrip=True)
(R/'normal-io.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
