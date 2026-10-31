from pathlib import Path
import json,hashlib
p=Path('D:/graghRAG-agent/.tmp')
a=p/'rust-bridge-coverage-20261028'
r=p/'rust-coverage-independent-review-20261028/actual-20261029'
for base in (a,r):
 j=json.loads((base/'final61-export.stdout').read_text())['data'][0]
 f=[f for f in j['files'] if f['filename'].startswith('/source/')]
 assert len(f)==1
 br=f[0]['branches'];assert len(br)==12 and sum(v>0 for row in br for v in row[4:6])==23
 da=[row for row in (base/'final61-lcov.stdout').read_text().splitlines() if row.startswith('DA:')]
 assert len(da)==60 and sum(int(row.split(',')[1])>0 for row in da)==59
print('Root readonly raw LLVM/LCOV arithmetic: author and independent 59/60 lines,23/24 branches; exit0')
