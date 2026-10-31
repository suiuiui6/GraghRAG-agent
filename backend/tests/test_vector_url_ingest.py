"""URL originals are streamed, bounded and retained without remote services."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import pytest
import socket
import ipaddress


@pytest.fixture(autouse=True)
def local_network_only(monkeypatch):
    connect = socket.socket.connect
    def guarded(sock, address):
        if isinstance(address, tuple):
            assert ipaddress.ip_address(address[0]).is_loopback, "Synthetic URL tests prohibit external connections"
        return connect(sock, address)
    monkeypatch.setattr(socket.socket, "connect", guarded)
from tests.test_vector_http_lifecycle import http_env


@pytest.fixture
def origin():
    control = {'body': b'%PDF-synthetic-original', 'redirect': None, 'requests': 0, 'headers': {}}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            control['requests'] += 1
            if control['redirect']:
                self.send_response(302)
                self.send_header('Location', control['redirect'])
                self.end_headers()
                return
            self.send_response(200)
            for name, value in control['headers'].items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(control['body'])
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    control['url'] = f'http://127.0.0.1:{server.server_port}/source.pdf?signature=synthetic-private'
    yield control
    server.shutdown()
    thread.join(3)
    server.server_close()


def test_materialize_streams_exclusively_and_refuses_overlimit(tmp_path, origin):
    from services.vector_ingest import materialize_original
    target = tmp_path/'original.pdf'
    materialize_original(origin['url'], target, max_bytes=100, address_allowed=lambda ip: True)
    assert target.read_bytes() == origin['body']
    with pytest.raises(FileExistsError):
        materialize_original(origin['url'], target, max_bytes=100, address_allowed=lambda ip: True)
    assert target.read_bytes() == origin['body']
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(origin['url'], tmp_path/'large.pdf', max_bytes=2, address_allowed=lambda ip: True)
    assert not (tmp_path/'large.pdf').exists()


def test_loopback_and_redirect_to_private_are_rejected(tmp_path, origin):
    from services.vector_ingest import materialize_original
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(origin['url'], tmp_path/'blocked.pdf', max_bytes=100)
    assert not (tmp_path/'blocked.pdf').exists()
    origin['redirect'] = 'http://169.254.169.254/latest/meta-data/'
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(origin['url'], tmp_path/'redirect.pdf', max_bytes=100,
                             address_allowed=lambda ip: str(ip) == '127.0.0.1')
    assert not (tmp_path/'redirect.pdf').exists()


def test_url_download_failure_has_safe_http_task_error(http_env, origin, monkeypatch):
    import worker
    def forbidden(*args, **kwargs):
        pytest.fail("Rejected source must not reach any provider")
    monkeypatch.setattr(worker, "run_real_pipeline", forbidden)
    client, service, headers, _ = http_env
    response = client.post('/api/v1/ingest', headers=headers(), data={'url':origin['url']})
    assert response.status_code == 200
    status = client.get(response.json()['links']['status'], headers=headers()).json()
    assert status['status'] == 'failed'
    assert status['error']['code'] == 'source_download_failed'
    assert 'signature' not in str(status)


def test_remote_original_reaches_publication_as_local_immutable_asset(http_env, origin, monkeypatch):
    from routes import ingest
    import worker
    from services import vector_ingest
    from doc_processor import Chunk
    client, service, headers, _ = http_env
    download = vector_ingest.materialize_original
    monkeypatch.setattr(vector_ingest, 'materialize_original',
        lambda url, target, **kw: download(url, target, **kw, address_allowed=lambda ip: True))
    seen = {}
    def pipeline(task_id, filepath, filename, progress, options):
        seen['original'] = filepath
        return {'document_id':'doc_url','kg_nodes':0,'kg_edges':0,'grounded_entities':0,
                'entity_types':0,'pages_parsed':1,'kg_path':'',
                '_publication_chunks':[Chunk('c1','source text','text')],
                '_publication_embeddings':[[1.0,0.0]]}
    monkeypatch.setattr(worker, 'run_real_pipeline', pipeline)
    response = client.post('/api/v1/ingest', headers=headers(), data={'url':origin['url']})
    assert response.status_code == 200, response.text
    status = client.get(response.json()['links']['status'], headers=headers()).json()
    assert status['status'] == 'done', status
    assert not seen['original'].startswith(('http://','https://'))
    assert Path(seen['original']).read_bytes() == origin['body']
    assert origin['requests'] == 1
    document = service.documents()[0]
    assert Path(document['filepath']).read_bytes() == origin['body']
    assert document['file_size_bytes'] == len(origin['body'])
    assert document['filename'] == 'source.pdf'


@pytest.mark.parametrize('url', ['http://user:password@example.org/a.pdf', 'file:///etc/passwd',
                               'http://127.0.0.1/a.pdf', 'http://[::1]/a.pdf',
                               'http://169.254.169.254/a.pdf'])
def test_unsafe_url_is_rejected_without_asset(tmp_path, url):
    from services.vector_ingest import materialize_original
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(url, tmp_path/'asset.pdf', max_bytes=100)
    assert not (tmp_path/'asset.pdf').exists()


def test_mixed_public_private_dns_is_rejected_before_connect(tmp_path, monkeypatch):
    from services import vector_ingest
    monkeypatch.setattr(vector_ingest, '_resolve', lambda *args:['8.8.8.8','127.0.0.1'])
    with pytest.raises(ValueError, match='source_download_failed'):
        vector_ingest.materialize_original('http://example.org/source.pdf', tmp_path/'asset.pdf', max_bytes=100)
    assert not (tmp_path/'asset.pdf').exists()


def test_redirect_limit_is_bounded(tmp_path, origin):
    from services.vector_ingest import materialize_original
    origin['redirect'] = origin['url']
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(origin['url'],tmp_path/'asset.pdf',max_bytes=100,max_redirects=2,
                             address_allowed=lambda ip:True)
    assert not (tmp_path/'asset.pdf').exists()


def test_validated_address_is_pinned_without_hostname_reresolution(tmp_path, origin, monkeypatch):
    from services import vector_ingest
    resolutions = []
    def resolve(host, port, timeout):
        resolutions.append(host)
        return ['127.0.0.1']
    monkeypatch.setattr(vector_ingest, '_resolve', resolve)
    dns = socket.getaddrinfo
    connections = []
    def numeric_only(host, *args, **kwargs):
        connections.append(host)
        assert host == '127.0.0.1'
        return dns(host, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', numeric_only)
    url = origin['url'].replace('127.0.0.1', 'synthetic.example')
    vector_ingest.materialize_original(url, tmp_path/'asset.pdf', max_bytes=100,
                                       address_allowed=lambda ip: ip.is_loopback)
    assert resolutions == ['synthetic.example']
    assert connections == ['127.0.0.1']
    assert (tmp_path/'asset.pdf').read_bytes() == origin['body']


@pytest.mark.parametrize('headers', [{'Content-Length':'9999'}, {'Content-Length':'-1'},
                                    {'Content-Encoding':'gzip'}, {'Content-Length':'not-a-number'}])
def test_invalid_response_headers_fail_without_partial_asset(tmp_path, origin, headers):
    from services.vector_ingest import materialize_original
    origin['headers'] = headers
    with pytest.raises(ValueError, match='source_download_failed'):
        materialize_original(origin['url'],tmp_path/'asset.pdf',max_bytes=100,
                             address_allowed=lambda ip:ip.is_loopback)
    assert not (tmp_path/'asset.pdf').exists()


@pytest.mark.parametrize('phase', ['headers', 'body'])
def test_total_deadline_interrupts_continuously_dripping_origin(tmp_path, phase):
    import time
    import threading
    from services.vector_ingest import materialize_original
    stop = threading.Event()
    class Dripping(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                self.wfile.write(b'HTTP/1.1 200 OK\r\n')
                if phase == 'body':
                    self.wfile.write(b'Content-Length: 100\r\n\r\n')
                self.wfile.flush()
                for _ in range(30):
                    self.wfile.write(b'X-Slow: a\r\n' if phase == 'headers' else b'a')
                    self.wfile.flush()
                    if stop.wait(.05):
                        return
                self.wfile.write(b'Content-Length: 1\r\n\r\na' if phase == 'headers' else b'')
                self.wfile.flush()
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Dripping)
    serving = Thread(target=server.serve_forever, daemon=True)
    serving.start()
    before = {t.ident for t in threading.enumerate() if t.name.startswith('ingest-deadline-')}
    target = tmp_path/'slow.pdf'
    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match='source_download_failed'):
            materialize_original(f'http://127.0.0.1:{server.server_port}/source.pdf', target,
                                 max_bytes=100, timeout=.2, address_allowed=lambda ip:ip.is_loopback)
        elapsed = time.monotonic() - started
        assert elapsed < .6, f'total deadline bypassed: {elapsed}'
        assert not target.exists()
        assert {t.ident for t in threading.enumerate() if t.name.startswith('ingest-deadline-')} == before
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        serving.join(3)



def test_https_deadline_transport_preserves_certificate_hostname_and_sni(tmp_path, monkeypatch):
    import ssl
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from services import vector_ingest
    hostname = 'synthetic.example'
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
            .not_valid_after(now+timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
            .sign(key, hashes.SHA256()))
    certfile, keyfile = tmp_path/'cert.pem', tmp_path/'key.pem'
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    sni = []
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile, keyfile)
    context.set_servername_callback(lambda sock, server_name, ctx:sni.append(server_name))
    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', '3')
            self.end_headers()
            self.wfile.write(b'tls')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    serving = Thread(target=server.serve_forever, daemon=True)
    serving.start()
    trusted = ssl.create_default_context(cafile=str(certfile))
    assert trusted.check_hostname and trusted.verify_mode == ssl.CERT_REQUIRED
    monkeypatch.setattr(ssl, '_create_default_https_context', lambda:trusted)
    monkeypatch.setattr(vector_ingest, '_resolve', lambda *args:['127.0.0.1'])
    try:
        target = tmp_path/'original.pdf'
        vector_ingest.materialize_original(f'https://{hostname}:{server.server_port}/source.pdf', target,
                                          max_bytes=100, address_allowed=lambda ip:ip.is_loopback)
        assert target.read_bytes() == b'tls'
        assert sni == [hostname]
    finally:
        server.shutdown()
        server.server_close()
        serving.join(3)
