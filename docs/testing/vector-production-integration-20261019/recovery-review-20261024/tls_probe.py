import sys, pathlib, datetime, ssl, socket, threading, http.client, os, json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
sys.path.insert(0,r'C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend')
from services import vector_ingest as vi
root=pathlib.Path(__file__).parent
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'synthetic.example')])
now=datetime.datetime.now(datetime.timezone.utc)
cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('synthetic.example')]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(key,hashes.SHA256()))
certfile=root/'synthetic.crt';keyfile=root/'synthetic.key'
certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM));keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
seen={'sni':[],'host':[],'connect':[]}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        seen['host'].append(self.headers['Host'])
        self.send_response(200);self.send_header('Content-Length','4');self.end_headers();self.wfile.write(b'data')
    def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certfile,keyfile)
context.set_servername_callback(lambda sock, name, context:seen['sni'].append(name))
server.socket=context.wrap_socket(server.socket,server_side=True)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
ssl._create_default_https_context=lambda: ssl.create_default_context(cafile=certfile)
vi._resolve=lambda *a:['127.0.0.1']
original_connect=socket.create_connection
def numeric_only(address,*a,**kw):
    seen['connect'].append(address[0]);assert address[0]=='127.0.0.1'
    return original_connect(address,*a,**kw)
socket.create_connection=numeric_only
for env in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY']:os.environ[env]='http://127.0.0.1:1'
try:
    file=root/'tls-original.pdf'
    file.unlink(missing_ok=True)
    vi.materialize_original(f'https://synthetic.example:{server.server_port}/a.pdf',file,max_bytes=4,address_allowed=lambda ip:ip.is_loopback)
    assert file.read_bytes()==b'data'
    assert seen['sni']==['synthetic.example']
    assert seen['host']==[f'synthetic.example:{server.server_port}']
    try:
        vi.materialize_original(f'https://wrong.example:{server.server_port}/a.pdf',root/'tls-wrong.pdf',max_bytes=4,address_allowed=lambda ip:ip.is_loopback)
        raise AssertionError('wrong TLS hostname accepted')
    except ValueError as exc: assert str(exc)=='source_download_failed'
    assert not (root/'tls-wrong.pdf').exists()
finally:
    socket.create_connection=original_connect;server.shutdown();server.server_close();thread.join()
    keyfile.unlink();certfile.unlink()
result={'original_hostname_verified':True,'wrong_hostname_rejected':True,'environment_proxy_ignored':True,**seen}
print(json.dumps(result,indent=2));(root/'tls-result.json').write_text(json.dumps(result,indent=2))
