"""SQLite 分片存储，复用冻结 R8 数值、过滤及资源算法。"""
from __future__ import annotations
import json, math, sqlite3, heapq, tempfile, pickle, functools, hashlib, hmac
from contextlib import closing, contextmanager
from contextvars import ContextVar
from services.document_catalog_schema import EXTRA_TABLE_SQL, install_catalog_schema
from pathlib import Path
import numpy as np
from vector_errors import VectorStoreError, VectorInputError, VectorStorageError
from vector_numeric import parse, record_ingress
from vector_runtime import connect, SyntheticIntegrationConfig, require_admission
from sqlite_vector_payload import temporary_directory

DEFAULT_COLLECTION='rag_docs'
DEFAULT_DIM=512
VECTORDB_DIR=str(Path(__file__).parent/'output'/'vectordb')


def boundary(operation):
    def decorate(fn):
        @functools.wraps(fn)
        def call(*a,**kw):
            try:return fn(*a,**kw)
            except VectorStoreError:raise
            except Exception as exc:raise VectorStorageError('storage_unavailable',operation) from exc
        return call
    return decorate


def fail(code='invalid_input',op='encode'):raise VectorInputError(code,op)


def ingress(v, query=False):
    if type(v) not in (int,float):return v
    try:
        if not query and type(v) is int and not -(2**63)<=v<2**63:v=float(v)
        tag,value=parse(json.dumps(v)) if query else record_ingress(v)
        if query and tag=='u64' and value>=2**63:fail('invalid_filter','compile')
        return 0.0 if not query and type(value) is float and value==0 else value
    except (ValueError,OverflowError) as exc:raise VectorInputError('invalid_filter' if query else 'invalid_input','compile' if query else 'encode') from exc


def compile_where(where):
    if where is None:return lambda m:True
    stack=[(where,False)]; result=[]; active=set()
    while stack:
        node,done=stack.pop()
        if done:
            active.remove(id(node)); key,value=next(iter(node.items())); count=len(value)
            children=result[-count:];del result[-count:]
            result.append((key,children));continue
        if type(node) is not dict or len(node)!=1:fail('invalid_filter','compile')
        key,value=next(iter(node.items()))
        if type(key) is not str:fail('invalid_filter','compile')
        if key in ('$and','$or'):
            if type(value) is not list or len(value)<2 or id(node) in active:fail('invalid_filter','compile')
            active.add(id(node));stack.append((node,True));stack.extend((x,False) for x in reversed(value));continue
        if key.startswith('$'):fail('invalid_filter','compile')
        if type(value) is not dict:value={'$eq':value}
        if len(value)!=1:fail('invalid_filter','compile')
        op,arg=next(iter(value.items()))
        if op not in ('$eq','$ne','$gt','$gte','$lt','$lte','$in','$nin'):fail('invalid_filter','compile')
        args=arg if op in ('$in','$nin') else [arg]
        if type(args) is not list or not args or any(type(x) is not type(args[0]) for x in args):fail('invalid_filter','compile')
        if type(args[0]) not in (str,bool,int,float):fail('invalid_filter','compile')
        if op in ('$gt','$gte','$lt','$lte') and type(arg) not in (int,float):fail('invalid_filter','compile')
        if op in ('$in','$nin') and type(args[0]) in (int,float):
            try:values=[parse(json.dumps(x)) for x in args]
            except (ValueError,OverflowError) as exc:raise VectorInputError('invalid_filter','compile') from exc
            if values[0][0]=='f64':args=[float(v) for _,v in values]
            else:
                if any(t=='f64' or v>=2**63 for t,v in values):fail('invalid_filter','compile')
                args=[v for _,v in values]
        else:args=[ingress(x,True) for x in args]
        result.append(('leaf',key,op,args))
    tree=result[0]
    def match(meta):
        todo=[(tree,False)];values=[]
        while todo:
            node,done=todo.pop()
            if node[0]!='leaf':
                if not done:todo.append((node,True));todo.extend((x,False) for x in reversed(node[1]));continue
                n=len(node[1]);xs=values[-n:];del values[-n:];values.append(all(xs) if node[0]=='$and' else any(xs));continue
            _,key,op,args=node
            def scalar(q):
                negative=op in ('$ne','$nin')
                if key not in meta:return negative
                stored=meta[key]
                if type(q) in (int,float):
                    if type(stored) not in (int,float):return negative
                    q=min(2**63-1,max(-(2**63),math.trunc(q))) if type(stored) is int else float(q)
                elif type(stored) is not type(q):return negative
                if op in ('$eq','$in'):return stored==q
                if negative:return stored!=q
                if op=='$gt':return stored>q
                if op=='$gte':return stored>=q
                if op=='$lt':return stored<q
                return stored<=q
            values.append(all(scalar(q) for q in args) if op=='$nin' else any(scalar(q) for q in args))
        return values[0]
    return match


# Logical payloads are split into 64KiB database rows. Public logical lengths
# are not constrained by this internal segment target.
SEGMENT=65536

class _StreamJSON:
    def __init__(self,value):self.value=value

def nested_json_parts(value,active=None):
    active=set() if active is None else active
    if type(value) is str:
        yield '"'
        for i in range(0,len(value),8192):yield json.dumps(value[i:i+8192])[1:-1]
        yield '"'
    elif value is None or type(value) in (bool,int,float):yield json.dumps(value)
    elif type(value) in (list,tuple,dict):
        if id(value) in active:fail()
        active.add(id(value));mapping=type(value) is dict
        yield '{' if mapping else '['
        for index,item in enumerate(value.items() if mapping else value):
            if index:yield ', '
            if mapping:
                key,item=item
                if type(key) is not str:fail()
                yield from nested_json_parts(key,active);yield ': '
            yield from nested_json_parts(item,active)
        yield '}' if mapping else ']'
        active.remove(id(value))
    else:fail()

def put_stream(c,seq,field,chunks):
    pending=bytearray();part=0
    for chunk in chunks:
        for offset in range(0,len(chunk),SEGMENT):
            pending.extend(chunk[offset:offset+SEGMENT])
            while len(pending)>=SEGMENT:
                c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,bytes(pending[:SEGMENT])));del pending[:SEGMENT];part+=1
    if pending:c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,bytes(pending)))


def read_payload(c,seq,field):
    return b''.join(row[0] for row in c.execute('SELECT data FROM payload WHERE seq=? AND field=? ORDER BY part',(seq,field)))


def text_parts(text):
    for i in range(0,len(text),8192):yield text[i:i+8192].encode('utf8')


def json_parts(meta):
    # Flat metadata only: encode string windows without a logical-string-sized
    # JSON escaped copy. Numeric formatting remains the existing parser contract.
    def string_parts(value):
        yield b'"'
        for i in range(0,len(value),8192):yield json.dumps(value[i:i+8192],ensure_ascii=False)[1:-1].encode('utf8')
        yield b'"'
    yield b'{'
    for index,(key,value) in enumerate(meta.items()):
        if index:yield b','
        yield from string_parts(key);yield b':'
        if type(value) is _StreamJSON:
            yield b'"'
            for piece in nested_json_parts(value.value):
                for start in range(0,len(piece),8192):yield json.dumps(piece[start:start+8192],ensure_ascii=False)[1:-1].encode('utf8')
            yield b'"'
        elif type(value) is str:yield from string_parts(value)
        else:yield json.dumps(value,allow_nan=False).encode('ascii')
    yield b'}'


def vector_parts(v,query=False):
    # Inspect container and scalar types before any NumPy coercion hook.
    if type(v) not in (list,tuple,np.ndarray):fail()
    if type(v) is np.ndarray and (v.ndim!=1 or v.dtype.kind not in 'iuf'):fail()
    if not len(v):fail('invalid_dimension')
    for start in range(0,len(v),8192):
        part=v[start:start+8192]
        if type(v) is not np.ndarray and any(type(x) not in (int,float) for x in part):fail()
        try:
            if not all(math.isfinite(x) for x in part):fail()
            with np.errstate(over='ignore'):a=np.array(part,dtype='<f4')
        except (ValueError,OverflowError,TypeError) as exc:raise VectorInputError('invalid_input','encode') from exc
        # finite binary64 that overflows f32 follows actual add oracle rejection.
        if not query and not np.isfinite(a).all():fail()
        yield a.tobytes()


class Collection:
    def __init__(self,store):self.s=store
    @boundary('encode')
    def add(self,ids,embeddings,documents=None,metadatas=None):
        if type(ids) is not list or not ids or any(type(i) is not str or not i for i in ids) or len(set(ids))!=len(ids):fail()
        if type(embeddings) not in (list,tuple,np.ndarray):fail()
        if type(embeddings) is np.ndarray and embeddings.ndim!=2:fail()
        if len(embeddings)!=len(ids):fail()
        if documents is not None and (type(documents) not in (list,tuple) or len(documents)!=len(ids)):fail()
        if metadatas is not None and (type(metadatas) not in (list,tuple) or len(metadatas)!=len(ids)):fail()
        # A private on-disk SQLite stage validates the complete batch before the
        # target transaction; no batch-sized vector matrix or encoded payload.
        with temporary_directory(dir=self.s.persist_dir) as directory:
            stage=Path(directory)/'stage.sqlite'
            with closing(connect(stage)) as t:
                t.execute('CREATE TABLE payload(seq INTEGER,field TEXT,part INTEGER,data BLOB,PRIMARY KEY(seq,field,part))')
                t.execute('CREATE TABLE staged(seq INTEGER,id TEXT,dimension INTEGER)')
                dimension=None
                for index,identifier in enumerate(ids):
                    vector=embeddings[index]
                    for count,blob in enumerate(vector_parts(vector)):
                        t.execute('INSERT INTO payload VALUES (?,?,?,?)',(index,'vector',count,blob))
                    dim=len(vector)
                    if dimension is not None and dim!=dimension:fail('invalid_dimension')
                    dimension=dim
                    text='' if documents is None else documents[index]
                    if type(text) is not str:fail()
                    meta={} if metadatas is None else metadatas[index]
                    if type(meta) is not dict or any(type(k) is not str or type(v) not in (str,int,float,bool,_StreamJSON) for k,v in meta.items()):fail()
                    compatible={k:ingress(v) for k,v in meta.items()}
                    put_stream(t,index,'document',text_parts(text))
                    put_stream(t,index,'metadata',json_parts(compatible))
                    t.execute('INSERT INTO staged VALUES (?,?,?)',(index,identifier,dim))
                t.commit()
                with closing(connect(self.s.path)) as c,c:
                    c.execute('BEGIN IMMEDIATE')
                    old=c.execute('SELECT dimension FROM collections WHERE name=?',(self.s.collection_name,)).fetchone()[0]
                    if old is not None and old!=dimension:fail('invalid_dimension')
                    c.execute('UPDATE collections SET dimension=? WHERE name=?',(dimension,self.s.collection_name))
                    for index,identifier,dim in t.execute('SELECT * FROM staged ORDER BY seq'):
                        cursor=c.execute('INSERT OR IGNORE INTO records(collection,id) VALUES (?,?)',(self.s.collection_name,identifier))
                        if cursor.rowcount==0:continue
                        seq=cursor.lastrowid
                        for field,part,data in t.execute('SELECT field,part,data FROM payload WHERE seq=? ORDER BY field,part',(index,)):
                            c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,data))
    def count(self):return self.s.count()
    @boundary('read')
    def get(self,ids=None,where=None,include=None,limit=None,offset=0,*,connection=None):
        if ids is not None and (type(ids) is not list or not ids or len(set(ids))!=len(ids)):fail(op='read')
        if type(offset) is not int or offset<0 or (limit is not None and (type(limit) is not int or limit<0)):fail(op='read')
        match=compile_where(where); wanted=None if ids is None else set(ids)
        out={'ids':[],'documents':[],'metadatas':[]};seen=0
        pages=self.s.iter_record_pages(connection=connection)
        try:
            for page in pages:
                for identifier,text,meta in zip(page['ids'],page['documents'],page['metadatas']):
                    if (wanted is not None and identifier not in wanted) or not match(meta):continue
                    if seen<offset:seen+=1;continue
                    if limit is not None and len(out['ids'])>=limit:return out
                    out['ids'].append(identifier);out['documents'].append(text);out['metadatas'].append(meta)
            return out
        finally:pages.close()
    @boundary('encode')
    def delete(self,ids=None,where=None):
        match=compile_where(where); wanted=None if ids is None else set(ids)
        with closing(connect(self.s.path)) as c,c:
            for seq,identifier in c.execute('SELECT seq,id FROM records WHERE collection=?',(self.s.collection_name,)):
                if wanted is not None and identifier not in wanted:continue
                if match(json.loads(read_payload(c,seq,'metadata'))):c.execute('DELETE FROM records WHERE seq=?',(seq,))


TABLE_SQL=(
    'CREATE TABLE collections(name TEXT PRIMARY KEY,dimension INTEGER,embedding_model TEXT NOT NULL,model_fingerprint TEXT NOT NULL)',
    'CREATE TABLE records(seq INTEGER PRIMARY KEY AUTOINCREMENT,collection TEXT NOT NULL,id TEXT NOT NULL,UNIQUE(collection,id))',
    'CREATE TABLE payload(seq INTEGER REFERENCES records(seq) ON DELETE CASCADE,field TEXT,part INTEGER,data BLOB,PRIMARY KEY(seq,field,part))',
)

def validate_schema(c):
    expected={('table',name,name,sql) for name,sql in zip(('collections','records','payload'),TABLE_SQL)}
    expected.add(('table','sqlite_sequence','sqlite_sequence','CREATE TABLE sqlite_sequence(name,seq)'))
    for name in ('collections','records','payload'):
        expected.add(('index','sqlite_autoindex_'+name+'_1',name,None))
    actual=set(c.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema'))
    expected.update(('table', name, name, sql) for name,sql in EXTRA_TABLE_SQL.items())
    for name,indexes in (('documents',1),('document_revisions',2),('document_tasks',1),('document_cleanup',1),('document_pins',1)):
        for number in range(1,indexes+1):expected.add(('index',f'sqlite_autoindex_{name}_{number}',name,None))
    if actual!=expected or c.execute('PRAGMA user_version').fetchone()!=(2,):raise VectorStorageError('schema_mismatch','open')
    if c.execute('PRAGMA foreign_key_check').fetchone() is not None:raise VectorStorageError('schema_mismatch','open')

class VectorStore:
    @boundary('open')
    def __init__(self,collection_name=DEFAULT_COLLECTION,persist_dir=None,embedding_dim=DEFAULT_DIM,*,embedding_model='BAAI/bge-small-zh-v1.5',integration_config=None,synthetic_config=None):
        if type(collection_name) is not str or not collection_name or type(embedding_dim) is not int or embedding_dim<1:fail()
        self.collection_name=collection_name;self.persist_dir=str(Path(persist_dir or VECTORDB_DIR).resolve());self.embedding_dim=embedding_dim
        if integration_config is not None and synthetic_config is not None:fail()
        admission=integration_config if integration_config is not None else synthetic_config
        require_admission(self.persist_dir,admission)
        if type(embedding_model) is not str or not embedding_model:fail()
        self.embedding_model=embedding_model
        self.model_fingerprint=hashlib.sha256(embedding_model.encode('utf-8')).hexdigest()
        self.integration_config=admission
        self.synthetic_config=admission
        self.path=Path(self.persist_dir)/'vectors.sqlite'
        if (Path(self.persist_dir)/'chroma.sqlite3').exists() and not self.path.exists():
            raise VectorStorageError('migration_required','open')
        # Validate runtime before creating any new database or directory.
        from vector_runtime import probe_runtime
        probe_runtime()
        Path(self.persist_dir).mkdir(parents=True,exist_ok=True)
        existed=self.path.exists()
        with closing(connect(self.path)) as c,c:
            if existed:validate_schema(c)
            c.execute('PRAGMA journal_mode=WAL')
            if not existed:
                for sql in TABLE_SQL:c.execute(sql)
                install_catalog_schema(c)
                c.execute('PRAGMA user_version=2')
                validate_schema(c)
            existing=c.execute('SELECT dimension,embedding_model,model_fingerprint FROM collections WHERE name=?',(collection_name,)).fetchone()
            if existing is not None:
                if existing[0]!=embedding_dim:raise VectorStorageError('dimension_conflict','open')
                if existing[1:]!=(embedding_model,self.model_fingerprint):raise VectorStorageError('model_conflict','open')
            c.execute('INSERT OR IGNORE INTO collections VALUES (?,?,?,?)',(collection_name,embedding_dim,embedding_model,self.model_fingerprint))
        self._collection=Collection(self)
        self._snapshot_connection=ContextVar('vector_read_snapshot',default=None)
        self._snapshot_collections=ContextVar('vector_read_collections',default=None)
    @contextmanager
    def read_snapshot_connection(self, connection, *, collection_names=None):
        """Bind a caller-owned read transaction to this request's store context.

        ContextVar isolates concurrent threads/tasks. The caller owns BEGIN,
        rollback/commit and close; a generator must be consumed in this context.
        """
        if not isinstance(connection,sqlite3.Connection) or not connection.in_transaction:
            raise VectorInputError('invalid_input','read')
        database = connection.execute('PRAGMA database_list').fetchone()
        if database is None or Path(database[2]).resolve() != self.path.resolve():
            raise VectorInputError('invalid_input','read')
        if collection_names is not None and (type(collection_names) is not tuple or any(type(name) is not str or not name for name in collection_names)):
            raise VectorInputError('invalid_input','read')
        token=self._snapshot_connection.set(connection)
        scope_token=self._snapshot_collections.set(collection_names)
        try:
            yield self
        finally:
            self._snapshot_collections.reset(scope_token)
            self._snapshot_connection.reset(token)

    def _read_scope(self, column='collection'):
        # Only trusted internal snapshot callers provide names; SQL always binds
        # them as values. An explicit empty scope matches nothing.
        names=self._snapshot_collections.get()
        if names is None:
            names=(self.collection_name,)
        if not names:
            return '0', ()
        selected=column+' IN ('+','.join('?' for _ in names)+')'
        # Standalone synthetic collections preserve the low-level adapter
        # contract. Registered and reserved document collections always require
        # an active committed catalog revision, including direct public reads.
        visible=(f"(({column} NOT IN (SELECT collection_name FROM document_revisions) "
                 f"AND substr({column},1,9)<>'document_') OR {column} IN "
                 "(SELECT r.collection_name FROM document_revisions r JOIN documents d "
                 "ON d.document_id=r.document_id WHERE d.deleted=0 "
                 "AND d.active_revision=r.revision AND r.state='committed'))")
        return selected+' AND '+visible, names

    @contextmanager
    def read_snapshot(self):
        """目录、search 与 pages 共用的磁盘快照；退出时释放事务。"""
        with closing(connect(self.path,True)) as c:
            try:
                c.execute('BEGIN')
                current=c.execute('SELECT dimension,embedding_model,model_fingerprint FROM collections WHERE name=?',(self.collection_name,)).fetchone()
                if current is None:raise VectorStorageError('schema_mismatch','read')
                if current[0]!=self.embedding_dim:raise VectorStorageError('dimension_conflict','read')
                if current[1:]!=(self.embedding_model,self.model_fingerprint):raise VectorStorageError('model_conflict','read')
                yield c
            finally:
                c.rollback()

    @contextmanager
    def _reader(self,connection=None):
        if connection is None:connection=self._snapshot_connection.get()
        if connection is None:
            with self.read_snapshot() as c:yield c
        else:
            if not isinstance(connection,sqlite3.Connection) or not connection.in_transaction:
                raise VectorInputError('invalid_input','read')
            actual=connection.execute('PRAGMA database_list').fetchone()[2]
            if Path(actual).resolve()!=self.path.resolve():raise VectorInputError('invalid_input','read')
            current=connection.execute('SELECT dimension,embedding_model,model_fingerprint FROM collections WHERE name=?',(self.collection_name,)).fetchone()
            if current is None:raise VectorStorageError('schema_mismatch','read')
            if current[0]!=self.embedding_dim:raise VectorStorageError('dimension_conflict','read')
            if current[1:]!=(self.embedding_model,self.model_fingerprint):raise VectorStorageError('model_conflict','read')
            yield connection

    def iter_record_pages(self,page_size=256,*,connection=None):
        if type(page_size) is not int or page_size<1:fail(op='scan')
        def pages():
            try:
                with self._reader(connection) as c:
                    out={'ids':[],'documents':[],'metadatas':[]};page_bytes=0
                    clause,parameters=self._read_scope()
                    for seq,identifier in c.execute('SELECT seq,id FROM records WHERE '+clause+' ORDER BY seq',parameters):
                        logical=c.execute("SELECT COALESCE(SUM(length(data)),0) FROM payload WHERE seq=? AND field IN ('document','metadata')",(seq,)).fetchone()[0]+len(identifier)*4
                        if out['ids'] and (len(out['ids'])>=page_size or page_bytes+logical>8*1024*1024):
                            yield out
                            out={'ids':[],'documents':[],'metadatas':[]};page_bytes=0
                        out['ids'].append(identifier);out['documents'].append(read_payload(c,seq,'document').decode('utf8'));out['metadatas'].append(json.loads(read_payload(c,seq,'metadata')));page_bytes+=logical
                    if out['ids']:yield out
            except VectorStoreError:raise
            except Exception as exc:raise VectorStorageError('storage_unavailable','scan') from exc
        return pages()
    @boundary('count')
    def count(self,*,connection=None):
        clause,parameters=self._read_scope()
        with self._reader(connection) as c:return c.execute('SELECT COUNT(*) FROM records WHERE '+clause,parameters).fetchone()[0]
    def add_chunks(self,chunks,embeddings):
        if len(chunks)!=len(embeddings):raise VectorInputError('invalid_input','encode',length_mismatch=True)
        if not chunks:return
        self._collection.add(ids=[x.chunk_id for x in chunks],embeddings=embeddings,documents=[x.text for x in chunks],metadatas=[{k:('' if v is None else v) for k,v in _build_chroma_metadata(x,_stream=True).items()} for x in chunks])
    def delete_by_source(self,source_file):self._collection.delete(where={'source_file':source_file})
    def delete_by_chunk_ids(self,chunk_ids):
        if chunk_ids:self._collection.delete(ids=chunk_ids)
    def get_by_ids(self,chunk_ids,*,connection=None):
        if not chunk_ids:return []
        r=self._collection.get(ids=chunk_ids,connection=connection)
        return [dict(chunk_id=i,text=t,metadata=_parse_chroma_metadata(m)) for i,t,m in zip(r['ids'],r['documents'],r['metadatas'])]
    def list_sources(self):
        sources=set();pages=self.iter_record_pages()
        try:
            for p in pages:
                sources.update(m['source_file'] for m in p['metadatas'] if m.get('source_file'))
        finally:pages.close()
        return sorted(sources)
    def get_collection_info(self):return dict(name=self.collection_name,count=self.count(),dimension=self.embedding_dim,sources=len(self.list_sources()),persist_dir=self.persist_dir)
    def create_migration_collection(self,new_dim,suffix='_v2',*,embedding_model=None):return VectorStore(self.collection_name+suffix,self.persist_dir,new_dim,embedding_model=embedding_model or self.embedding_model,integration_config=self.integration_config)
    @boundary('read')
    def backup(self,snapshot):
        snapshot=Path(snapshot)
        with snapshot.open('xb'):pass
        try:
            with closing(connect(self.path,True)) as source,closing(connect(snapshot)) as dest:
                source.backup(dest,pages=256)
                if dest.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:fail(op='read')
            digest=hashlib.sha256();size=0
            with snapshot.open('rb') as f:
                while block:=f.read(65536):digest.update(block);size+=len(block)
            return dict(sha256=digest.hexdigest(),size=size)
        except BaseException:snapshot.unlink(missing_ok=True);raise
    @staticmethod
    @boundary('open')
    def restore(snapshot,target,*,sha256,size,collection_name=DEFAULT_COLLECTION,embedding_dim=DEFAULT_DIM,embedding_model='BAAI/bge-small-zh-v1.5',integration_config=None,synthetic_config=None):
        target=Path(target)
        require_admission(target,integration_config if integration_config is not None else synthetic_config)
        if target.exists():fail(op='open')
        if type(size) is not int or size<1 or type(sha256) is not str:fail(op='open')
        with temporary_directory(dir=target.parent) as stage_dir:
            stage=Path(stage_dir)/'verified.sqlite';digest=hashlib.sha256();actual=0
            with Path(snapshot).open('rb') as src,stage.open('xb') as dst:
                while block:=src.read(65536):
                    actual+=len(block)
                    if actual>size:fail(op='open')
                    digest.update(block);dst.write(block)
            if actual!=size or not hmac.compare_digest(digest.hexdigest(),sha256):fail(op='open')
            with closing(connect(stage,True)) as c:
                if c.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:fail(op='open')
                validate_schema(c)
            target.mkdir()
            try:
                with closing(connect(stage,True)) as src,closing(connect(target/'vectors.sqlite')) as dst:src.backup(dst,pages=256)
                return VectorStore(collection_name,str(target),embedding_dim,embedding_model=embedding_model,integration_config=integration_config,synthetic_config=synthetic_config)
            except BaseException:
                import shutil
                shutil.rmtree(target)
                raise
    @boundary('search')
    def search(self,query_vector,top_k=20,where=None,text_char_limit=None,metadata_keys=None,*,connection=None):
        if type(top_k) is not int or top_k<1:fail(op='search')
        match=compile_where(where)
        # HNSW cosine preprocessing uses f32 norm and f32 arithmetic.
        qnorm=np.float32(0)
        for blob in vector_parts(query_vector,query=True):
            with np.errstate(over='ignore',invalid='ignore'):
                for x in np.frombuffer(blob,dtype='<f4'):qnorm=np.float32(qnorm+np.float32(x*x))
        qnorm=np.float32(np.sqrt(qnorm)+np.float32(1e-30))
        heap=[]
        with self._reader(connection) as c:
            dim=c.execute('SELECT dimension FROM collections WHERE name=?',(self.collection_name,)).fetchone()[0]
            if dim is not None and dim!=len(query_vector):fail('invalid_dimension','search')
            clause,parameters=self._read_scope()
            collection_clause,collection_parameters=self._read_scope('name')
            for name,dim in c.execute('SELECT name,dimension FROM collections WHERE '+collection_clause,collection_parameters):
                if dim is not None and dim!=len(query_vector):fail('invalid_dimension','search')
            for seq,identifier in c.execute('SELECT seq,id FROM records WHERE '+clause+' ORDER BY seq',parameters):
                meta=json.loads(read_payload(c,seq,'metadata'))
                if not match(meta):continue
                norm=np.float32(0)
                for blob, in c.execute("SELECT data FROM payload WHERE seq=? AND field='vector' ORDER BY part",(seq,)):
                    for x in np.frombuffer(blob,dtype='<f4'):norm=np.float32(norm+np.float32(x*x))
                norm=np.float32(np.sqrt(norm)+np.float32(1e-30));dot=np.float32(0);start=0
                for blob, in c.execute("SELECT data FROM payload WHERE seq=? AND field='vector' ORDER BY part",(seq,)):
                    v=np.frombuffer(blob,dtype='<f4')*np.float32(1/norm)
                    with np.errstate(over='ignore',invalid='ignore'):
                        q=np.array(query_vector[start:start+len(v)],dtype='<f4')*np.float32(1/qnorm)
                        for a,b in zip(q,v):dot=np.float32(dot+np.float32(a*b))
                    start+=len(v)
                distance=float(np.float32(np.float32(1)-dot));score=1-distance/2
                item=(score,-seq,seq,identifier)
                if len(heap)<top_k:heapq.heappush(heap,item)
                elif item>heap[0]:heapq.heapreplace(heap,item)
            output=[]
            for score,_,seq,identifier in sorted(heap,reverse=True):
                text=read_payload(c,seq,'document').decode('utf8');meta=_parse_chroma_metadata(json.loads(read_payload(c,seq,'metadata')))
                if text_char_limit is not None:text=text[:text_char_limit]
                if metadata_keys is not None:meta={k:meta[k] for k in metadata_keys if k in meta}
                output.append(dict(chunk_id=identifier,text=text,score=round(score,4),source='vector',metadata=meta))
            return output


def create_vector_store(collection_name=DEFAULT_COLLECTION,embedding_dim=DEFAULT_DIM,persist_dir=None,**kwargs):return VectorStore(collection_name,persist_dir,embedding_dim,**kwargs)
def _build_chroma_metadata(chunk,_stream=False) -> dict:
    """Convert Chunk metadata to ChromaDB-compatible flat dict.

    ChromaDB metadata must be str, int, float, or bool only.
    Lists and dicts are serialized to JSON strings.
    """
    if chunk.metadata is None:
        return {
            "source_file": "",
            "source_format": "",
            "content_type": chunk.content_type,
            "page_idx": 0,
        }

    meta = chunk.metadata
    encode = _StreamJSON if _stream else json.dumps
    entity_types_json = encode(meta.entity_types) if meta.entity_types else "[]"
    section_path_json = encode(meta.section_path) if meta.section_path else "[]"
    entity_ids_json = encode(getattr(meta, "entity_ids", [])) if getattr(meta, "entity_ids", None) else "[]"

    return {
        "source_file": meta.source_file or "",
        "source_format": meta.source_format or "",
        "page_idx": meta.page_idx if meta.page_idx is not None else 0,
        "content_type": meta.content_type or chunk.content_type,
        "project_id": meta.project_id or "",
        "token_count": meta.token_count,
        "entity_types": entity_types_json,
        "section_path": section_path_json,
        "entity_ids": entity_ids_json,
        "char_start": meta.char_start,
        "char_end": meta.char_end,
    }


def _parse_chroma_metadata(meta: dict) -> dict:
    """Parse ChromaDB flat metadata back to structured dict."""
    if not meta:
        return {}

    result = dict(meta)

    # Deserialize JSON fields
    for field in ["entity_types", "section_path", "entity_ids"]:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                result[field] = []

    return result




