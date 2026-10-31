"""Fixed-scope full backend diagnostic; no success gate is silently bypassed."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
OUT = Path(__file__).parent / 'full-backend-20261027-r7'
PYTHON = Path(sys.argv[1]).resolve()
if not PYTHON.is_file():
    raise SystemExit('explicit verified Python runtime required')
OUT.mkdir(exist_ok=True)

def snapshot():
    paths = []
    for base, dirs, files in os.walk(ROOT / 'backend'):
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', 'output', 'uploads', 'node_modules', 'target'}
                   and not (Path(base) == ROOT / 'backend/tests' and d.startswith(('_sandbox_', '_tmp_', 'tmp_basetemp_', 'tmp_probe_')))]
        paths += [Path(base) / f for f in files if f.endswith('.py')]
    paths += [ROOT / 'backend/pyproject.toml', ROOT / 'backend/uv.lock', ROOT / 'backend/requirements.txt', ROOT / 'docs/testing/coverage-backend-2026-10-12.ini', ROOT / 'Dockerfile.backend', ROOT / 'docker-compose.yml', ROOT / 'docs/contracts/2026-10-14-vector-ingress-semantics.md', ROOT / 'docs/design/2026-10-19-vector-production-integration.md', ROOT / 'docs/plans/2026-10-19-vector-production-integration.md']
    native = ROOT / 'backend/native/vector_numeric'
    paths += [native / name for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', 'src/main.rs',
              'bin/x86_64-pc-windows-msvc/approved-build.json', 'bin/x86_64-pc-windows-msvc/vector-numeric-bridge.exe')]
    paths += [ROOT / 'docs/review/common-three-arm-20261015/registration.json',
              ROOT / 'docs/review/simple-output-20261016/registration-receipt.json',
              ROOT / 'docs/review/simple-output-20261016/prompts.v1.json']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

before = snapshot()
(OUT / 'before.json').write_text(json.dumps(before, indent=2))
env = dict(os.environ, PYTHONPATH=os.pathsep.join([
    'D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012', str(ROOT), str(ROOT / 'langextract'), str(ROOT / 'backend')]),
    PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
    GRAPHRAG_FROZEN_TEST_ROOT='D:/graghRAG-agent',
    GRAPHRAG_TEST_MODEL_RECEIPT='D:/graghRAG-agent/.tmp/vector-backend-runtime-20261020/model-encode-receipt.json')
config = 'docs/testing/coverage-backend-2026-10-12.ini'
commands = []
def run(name, args):
    started = time.monotonic()
    command = [str(PYTHON), *args]
    with (OUT / (name + '.log')).open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
    commands.append({'name': name, 'command': command, 'exit': code, 'elapsed_seconds': time.monotonic() - started})
    (OUT / 'commands.json').write_text(json.dumps(commands, indent=2))
    return code

run('tests', ['-m', 'coverage', 'run', '--rcfile=' + config, '--data-file=' + str(OUT / 'backend.coverage'),
              str(ROOT / 'backend/tests/model_dependency_bootstrap.py'), 'backend/tests', 'backend/research/test_deepseek_scope_pilot.py', '-vv', '-ra', '--tb=short', '--durations=20',
              '-p', 'no:cacheprovider', '--basetemp=' + str(OUT / 'test-temp'), '--junitxml=' + str(OUT / 'junit.xml')])
run('export', ['-m', 'coverage', 'json', '--rcfile=' + config, '--data-file=' + str(OUT / 'backend.coverage'),
               '-o', str(OUT / 'coverage.json')])
after = snapshot()
(OUT / 'after.json').write_text(json.dumps(after, indent=2))
summary = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'commands': commands,
           'inputs_stable': before == after, 'purpose': 'full fixed-scope backend verification; dependency preparation inside coverage precedes pytest; total tests command budget remains 1200 seconds'}
if (OUT / 'coverage.json').exists():
    report = json.loads((OUT / 'coverage.json').read_text())
    production = {p for p in before if p.endswith('.py') and '/tests/' not in p and '/research/test_' not in p}
    measured = {p.replace('\\', '/') for p in report['files']}
    summary.update(totals=report['totals'], production_count=len(production), coverage_count=len(measured),
                   missing=sorted(production - measured), extra=sorted(measured - production))
totals = summary.get('totals', {})
summary['coverage_gate'] = bool(totals and totals['covered_lines'] * 100 >= totals['num_statements'] * 90
                                and totals['covered_branches'] * 100 >= totals['num_branches'] * 90)
summary['scope_gate'] = summary.get('missing') == [] and summary.get('extra') == []
summary['command_gate'] = all(item['exit'] == 0 for item in commands)
junit = OUT / 'junit.xml'
if junit.exists():
    suites = ET.parse(junit).getroot()
    cases = list(suites.iter('testcase'))
    summary['test_counts'] = {'collected': len(cases),
                              **{name: len(list(suites.iter(name))) for name in ('failure', 'error', 'skipped')}}
counts = summary.get('test_counts', {})
summary['test_gate'] = bool(summary['command_gate'] and counts.get('collected', 0) > 0
                            and all(counts.get(name) == 0 for name in ('failure', 'error', 'skipped')))
summary['backend_gate'] = summary['inputs_stable'] and summary['coverage_gate'] and summary['scope_gate'] and summary['test_gate']
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
sys.exit(0 if summary['backend_gate'] else 1)
