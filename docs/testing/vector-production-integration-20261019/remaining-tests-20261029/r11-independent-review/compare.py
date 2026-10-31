from pathlib import Path
import json,hashlib
O=Path('D:/graghRAG-agent/.tmp/r11-independent-review-20261029');R=Path('D:/graghRAG-agent/.tmp/vector-resume-20261022');a=json.loads((R/'full-backend-20261028-r10/before.json').read_text());b=json.loads((R/'full-backend-20261029-r11/before.json').read_text());print(json.dumps({'changed':[k for k in a.keys()&b.keys() if a[k]!=b[k]],'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys())},indent=2))
