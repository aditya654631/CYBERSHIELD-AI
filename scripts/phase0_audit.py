"""Non-destructive baseline audit. No application fixes, migrations or live writes.

Run with the project's virtualenv Python. Private backups/logs go under ignored
scratch/; reports must never include .env contents or database credentials.
"""
from pathlib import Path
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
STAMP = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT = ROOT / 'scratch' / ('phase0_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8', 'replace').strip()


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str), encoding='utf-8')


def run(name, command, cwd=ROOT, env=None, timeout=1800):
    started = time.monotonic()
    result = {'name': name, 'command': command, 'cwd': str(cwd)}
    with (OUT / (name + '.log')).open('w', encoding='utf-8') as log:
        try:
            p = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                               stderr=subprocess.STDOUT, timeout=timeout)
            result['exit_code'] = p.returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            result['error'] = type(e).__name__
    result['seconds'] = round(time.monotonic() - started, 2)
    save(name + '.result.json', result)
    print(json.dumps(result), flush=True)
    return result


baseline = {'utc': STAMP, 'head': git('rev-parse', 'HEAD'),
            'branch': git('branch', '--show-current'), 'status_before': git('status', '--short'),
            'private_backup_directory': str(OUT), 'database_backups': []}
save('baseline.json', baseline)
print('AUDIT_DIRECTORY=' + str(OUT), flush=True)
subprocess.run(['git', 'bundle', 'create', str(OUT / 'repository.bundle'), '--all'], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
run('git_bundle_verify', ['git', 'bundle', 'verify', str(OUT / 'repository.bundle')])

# Preserve the actual tracked working files, including uncommitted tracked edits.
tracked = git('ls-files', '-z').split('\0')
with zipfile.ZipFile(OUT / 'tracked_worktree.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in tracked:
        p = ROOT / name
        if p.is_file():
            z.write(p, name)
with zipfile.ZipFile(OUT / 'tracked_worktree.zip', 'r') as z:
    assert z.testzip() is None
for folder in ['ml/artifacts', 'ml/evaluation']:
    shutil.copytree(ROOT / folder, OUT / folder)

# Secret configuration stays private in ignored scratch, never printed.
for rel in ['.env', 'frontend/.env', 'frontend/.env.local']:
    p = ROOT / rel
    if p.exists():
        dest = OUT / 'private_config' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)

db_paths = sorted(set(list(ROOT.glob('*.db')) + list((ROOT / 'backend').glob('*.db'))))
for p in db_paths:
    dest = OUT / 'sqlite_backups' / p.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    record = {'source': str(p.relative_to(ROOT)), 'backup': str(dest.relative_to(OUT))}
    try:
        with sqlite3.connect(p.as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(dest) as target:
                src.backup(target)
                record['integrity_check'] = target.execute('PRAGMA integrity_check').fetchone()[0]
                record['tables'] = target.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        record['sha256'] = sha(dest)
    except Exception as e:
        record['error'] = type(e).__name__
    baseline['database_backups'].append(record)

# Inspect configured backend without printing credentials and without a DB connection.
try:
    from backend.app.config.settings import settings
    from sqlalchemy.engine import make_url
    url = make_url(settings.DATABASE_URL)
    baseline['configured_database_engine'] = url.get_backend_name()
    if url.get_backend_name() == 'postgresql':
        pg_dump = shutil.which('pg_dump')
        if pg_dump:
            pg_env = os.environ.copy()
            for key, value in {'PGHOST': url.host, 'PGPORT': str(url.port or 5432),
                               'PGUSER': url.username, 'PGPASSWORD': url.password,
                               'PGDATABASE': url.database, 'PGSSLMODE': url.query.get('sslmode', 'require'),
                               'PGCONNECT_TIMEOUT': '15'}.items():
                if value is not None:
                    pg_env[key] = value
            result = run('configured_postgres_backup', [pg_dump, '-Fc', '-f', str(OUT / 'configured_database.dump')], env=pg_env, timeout=180)
            baseline['configured_database_backup'] = result
        else:
            baseline['configured_database_backup'] = 'BLOCKED: pg_dump unavailable; local SQLite backups are NOT a backup of configured PostgreSQL.'
    else:
        baseline['configured_database_backup'] = 'Check configured SQLite file against database_backups; backups have integrity checks, not an application restore drill.'
except Exception as e:
    baseline['configured_database_inspection_error'] = type(e).__name__

baseline['artifact_hashes_before'] = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'ml/artifacts').glob('*') if p.is_file()}
save('baseline.json', baseline)
print('BACKUP_BASELINE_READY', flush=True)

env = os.environ.copy()
env.update({'ENVIRONMENT': 'test', 'DATABASE_URL': 'sqlite:///' + (OUT / 'test_bootstrap.db').as_posix(),
            'AUTO_SEED_DEMO_DATA': 'false', 'PYTHONIOENCODING': 'utf-8',
            'FABRIC_GATEWAY_URL': 'http://127.0.0.1:1/api/v1'})
jobs = [('pytest', [sys.executable, '-m', 'pytest', 'tests', '-q', '-ra', '--junitxml=' + str(OUT / 'pytest.xml')], ROOT, env)]
node = shutil.which('node')
if node:
    jobs.append(('frontend_build', [node, str(ROOT / 'frontend/node_modules/typescript/bin/tsc')], ROOT / 'frontend', env))
    for name, folder, test_dir in [('gateway', 'blockchain/gateway', 'tests'),
                                  ('feature_engine', 'blockchain/feature-engine', 'tests'),
                                  ('prediction_chaincode', 'blockchain/chaincode/prediction-audit', 'test'),
                                  ('geo_chaincode', 'blockchain/chaincode/geo-intelligence', 'test')]:
        mocha = ROOT / folder / 'node_modules/mocha/bin/mocha.js'
        if mocha.exists():
            jobs.append((name, [node, str(mocha), test_dir, '--recursive', '--timeout', '20000'], ROOT / folder, env))
        else:
            save(name + '.result.json', {'status': 'NOT_RUN', 'reason': 'local mocha dependency unavailable'})

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(run, *job) for job in jobs]
    results = [f.result() for f in futures]
if node and next(r for r in results if r['name'] == 'frontend_build').get('exit_code') == 0:
    results.append(run('frontend_vite_build', [node, str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), 'build', '--outDir', str(OUT / 'frontend_dist')], ROOT / 'frontend', env))

baseline['artifact_hashes_after'] = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'ml/artifacts').glob('*') if p.is_file()}
baseline['models_unchanged'] = baseline['artifact_hashes_before'] == baseline['artifact_hashes_after']
baseline['status_after'] = git('status', '--short')
save('baseline.json', baseline)
save('results.json', results)
print('AUDIT_FINISHED=' + str(OUT), flush=True)
