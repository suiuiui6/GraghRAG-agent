import sys, pathlib, json, hashlib, time, threading, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, r'C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend')
from vector_runtime import SyntheticStorageConfig, connect
from vector_store import VectorStore
from services.document_publication import DocumentPublication
from services.vector_backup import PublicationBackup
from services.vector_ingest import materialize_original
from doc_processor import Chunk
PROFILE={'model':'backup-fixed','revision':'sha','dimension':2,'normalize':True}
results = {}
for badmain in (True, False):
    with SyntheticStorageConfig.create() as config:
        store=VectorStore(persist_dir=str(config.root/'database'),embedding_dim=2,embedding_model=PROFILE['model'],synthetic_config=config)
        service=DocumentPublication(store, config.root/'assets', PROFILE)
        asset=service.asset_root/'one.txt'; asset.write_text('v1')
        service.publish('one','doc',{'owner_id':'owner'},[Chunk('c1','v1','text')],[[1.,0.]],assets=[{'path':'one.txt','sha256':hashlib.sha256(asset.read_bytes()).hexdigest()}])
        backup=PublicationBackup(service); snapshot=config.root/'backup';backup.create(snapshot)
        db=snapshot/'database/vectors.sqlite'; c=connect(db)
        try:
            c.execute('PRAGMA wal_autocheckpoint=0')
            c.execute('UPDATE documents SET active_revision=?',(999 if badmain else 1,));c.commit()
            c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchall()
            c.execute('UPDATE documents SET active_revision=?',(1 if badmain else 999,));c.commit()
            manifestfile=snapshot/'publication.json'; manifest=json.loads(manifestfile.read_text())
            raw=db.read_bytes();manifest['database']={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
            manifestfile.write_text(json.dumps(manifest))
            files={str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*') if p.is_file()}
            try:
                backup.verify(snapshot)
                verified=True
            except ValueError as e:
                verified=str(e)
            after={str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*') if p.is_file()}
            assert files == after, 'verification mutated archive'
            if badmain:
                assert verified == 'backup_catalog_integrity', verified
                try:
                    backup.restore(snapshot,config.root/'restore')
                    raise AssertionError('bad main restored')
                except ValueError as e:
                    assert str(e)=='backup_catalog_integrity'
                assert not (config.root/'restore').exists()
            else:
                assert verified is True, verified
                target=backup.restore(snapshot,config.root/'restore')
                restored=connect(target/'database/vectors.sqlite',True)
                try: assert restored.execute('SELECT active_revision FROM documents').fetchone()==(1,)
                finally: restored.close()
            results['badmain' if badmain else 'badwal']={'verify':verified,'archive_unchanged':files==after}
        finally: c.close()

class SlowHeaders(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.wfile.write(b'HTTP/1.1 200 OK\r\n');self.wfile.flush()
            for i in range(20):
                self.wfile.write(b'X-Slow: a\r\n');self.wfile.flush();time.sleep(.05)
            self.wfile.write(b'Content-Length: 1\r\n\r\na');self.wfile.flush()
        except OSError: pass
    def log_message(self,*a): pass
server=ThreadingHTTPServer(('127.0.0.1',0),SlowHeaders)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
target=pathlib.Path(__file__).parent/'slow.pdf'
started=time.monotonic()
try:
    materialize_original(f'http://127.0.0.1:{server.server_port}/source.pdf',target,max_bytes=10,timeout=.2,address_allowed=lambda ip:ip.is_loopback)
    outcome='success'
except ValueError as e: outcome=str(e)
elapsed=time.monotonic()-started
results['slow_header_deadline']={'budget_seconds':.2,'actual_seconds':elapsed,'outcome':outcome,'partial_file':target.exists()}
server.shutdown();server.server_close();thread.join()
print(json.dumps(results,indent=2))
pathlib.Path(__file__).with_suffix('.json').write_text(json.dumps(results,indent=2))
