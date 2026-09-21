"""Read-only, consistent configured PostgreSQL data snapshot; NOT a pg_dump replacement.

Contains sensitive operational records. Keep under ignored scratch, never commit.
Schema inventory and data preserve evidence; PostgreSQL restore drill remains separate.
"""
from pathlib import Path
import base64
import datetime
import decimal
import gzip
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[1]).resolve()
from backend.app.config.settings import settings
from sqlalchemy import create_engine, inspect, text


def encode(value):
    if isinstance(value, (bytes, memoryview)):
        return {'__type__': 'bytes', 'base64': base64.b64encode(bytes(value)).decode()}
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time, decimal.Decimal)):
        return {'__type__': type(value).__name__, 'value': str(value)}
    return str(value)


engine = create_engine(settings.DATABASE_URL, connect_args={'connect_timeout': 15}, echo=False)
summary = {'kind': 'READ_ONLY_DATA_SNAPSHOT_NOT_NATIVE_RESTORABLE_BACKUP', 'tables': [],
           'restore_verified': False}
try:
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout = '60000'"))
            inspector = inspect(conn)
            for schema in inspector.get_schema_names():
                if schema == 'information_schema' or schema.startswith('pg_'):
                    continue
                for table in inspector.get_table_names(schema=schema):
                    number = len(summary['tables']) + 1
                    dest = OUT / f'private_pg_table_{number:03}.jsonl.gz'
                    quote = engine.dialect.identifier_preparer.quote
                    query = f'SELECT * FROM {quote(schema)}.{quote(table)}'
                    count = 0
                    columns = inspector.get_columns(table, schema=schema)
                    with gzip.open(dest, 'wt', encoding='utf-8') as f:
                        f.write(json.dumps({'schema': schema, 'table': table,
                                            'columns': columns,
                                            'primary_key': inspector.get_pk_constraint(table, schema=schema),
                                            'foreign_keys': inspector.get_foreign_keys(table, schema=schema)}, default=encode) + '\n')
                        for row in conn.execute(text(query)).mappings():
                            f.write(json.dumps(dict(row), default=encode) + '\n')
                            count += 1
                    with gzip.open(dest, 'rt', encoding='utf-8') as f:
                        assert sum(1 for _ in f) - 1 == count
                    summary['tables'].append({'schema': schema, 'table': table, 'rows': count,
                                              'file': dest.name, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    summary['status'] = 'SNAPSHOT_COMPLETE_NATIVE_BACKUP_AND_RESTORE_PENDING'
except Exception as e:
    summary['status'] = 'INCOMPLETE'
    summary['error_type'] = type(e).__name__
finally:
    engine.dispose()
    (OUT / 'postgres_snapshot_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'status': summary['status'], 'tables': len(summary['tables']),
                      'rows': sum(t['rows'] for t in summary['tables']), 'restore_verified': False}))
