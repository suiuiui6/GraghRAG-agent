"""Exact catalog schema additions to the versioned vector database."""

EXTRA_TABLE_SQL = {
    'document_catalog_state': 'CREATE TABLE document_catalog_state(id INTEGER PRIMARY KEY CHECK(id=1),generation INTEGER NOT NULL)',
    'documents': 'CREATE TABLE documents(document_id TEXT PRIMARY KEY,identity_json TEXT NOT NULL,active_revision INTEGER,deleted INTEGER NOT NULL DEFAULT 0)',
    'document_revisions': "CREATE TABLE document_revisions(document_id TEXT NOT NULL REFERENCES documents(document_id),revision INTEGER NOT NULL,task_id TEXT NOT NULL UNIQUE,state TEXT NOT NULL CHECK(state IN ('prepared','committed','aborted')),assets_json TEXT NOT NULL,model_json TEXT NOT NULL,collection_name TEXT NOT NULL,metadata_json TEXT NOT NULL,PRIMARY KEY(document_id,revision))",
    'document_tasks': 'CREATE TABLE document_tasks(task_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,expected_revision INTEGER,revision INTEGER NOT NULL,status TEXT NOT NULL,error_code TEXT,result_json TEXT,request_hash TEXT NOT NULL)',
    'document_cleanup': 'CREATE TABLE document_cleanup(document_id TEXT NOT NULL,revision INTEGER NOT NULL,assets_json TEXT NOT NULL,status TEXT NOT NULL,error_code TEXT,attempts INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(document_id,revision))',
    'document_pins': 'CREATE TABLE document_pins(token TEXT PRIMARY KEY,document_id TEXT NOT NULL,revision INTEGER NOT NULL,owner_pid INTEGER NOT NULL)',
}


def install_catalog_schema(connection):
    """Initialize only in a caller-owned, already admitted new database."""
    for statement in EXTRA_TABLE_SQL.values():
        connection.execute(statement)
    connection.execute('INSERT INTO document_catalog_state VALUES (1,0)')
