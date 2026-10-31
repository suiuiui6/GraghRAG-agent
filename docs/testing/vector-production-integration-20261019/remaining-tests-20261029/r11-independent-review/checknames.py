from pathlib import Path
import email,json,re
V=Path('D:/graghRAG-agent/.tmp/backend-runtime-20261029/.venv/Lib/site-packages');A=Path('D:/graghRAG-agent/.tmp/installed-windows-audit-20261029');norm=lambda s:re.sub('[-_.]+','-',s.lower())
a={};b={}
for p in V.glob('*.dist-info/METADATA'):
 m=email.message_from_bytes(p.read_bytes());a[norm(m['Name'])]=m['Version']
for x in json.loads((A/'audit.json').read_text())['dependencies']:b[norm(x['name'])]=x['version']
print('only actual',[(k,v) for k,v in a.items() if k not in b]);print('only audit',[(k,v) for k,v in b.items() if k not in a]);print('versions',[(k,v,b[k]) for k,v in a.items() if k in b and v!=b[k]])
r=json.loads((A/'installed-metadata.json').read_text());print('record sample',r[-3:]);print('name diffs',set(a)-{norm(x['name']) for x in r})
