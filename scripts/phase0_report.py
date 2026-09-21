"""Summarize recorded Phase 0 runs; does not infer PS compliance from test counts."""
from pathlib import Path
import collections
import csv
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
DOC = ROOT / 'docs/phase0'
DOC.mkdir(parents=True, exist_ok=True)
tree = ET.parse(OUT / 'pytest.xml')
rows = []
groups = collections.Counter()
counts = collections.Counter()
for case in tree.iter('testcase'):
    failure = case.find('failure')
    error = case.find('error')
    skip = case.find('skipped')
    state = 'failed' if failure is not None else 'error' if error is not None else 'skipped' if skip is not None else 'passed'
    counts[state] += 1
    if state != 'passed':
        node = failure if failure is not None else error if error is not None else skip
        rows.append({'test': case.get('classname', '') + '::' + case.get('name', ''),
                     'status': state, 'message': node.get('message', '')})
        if state == 'failed':
            groups[case.get('classname')] += 1
with (DOC / 'TEST_FAILURES.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['test', 'status', 'message'])
    writer.writeheader()
    writer.writerows(rows)
baseline = json.loads((OUT / 'baseline.json').read_text())
summary = {'baseline_commit': baseline['head'], 'run_directory': str(OUT), 'pytest': dict(counts),
           'failure_groups': dict(groups), 'models_unchanged': baseline.get('models_unchanged'),
           'commands': json.loads((OUT / 'results.json').read_text()),
           'scope': 'Code inspection, isolated API/service tests and builds. No browser visual QA, real accuracy re-evaluation, live financial action, or production load test.'}
for name in ['postgres_snapshot_summary', 'stale_prediction_reproduction']:
    path = OUT / (name + '.json')
    if path.exists():
        value = json.loads(path.read_text())
        if name == 'postgres_snapshot_summary':
            value = {'status': value['status'], 'tables': len(value['tables']),
                     'rows': sum(t['rows'] for t in value['tables']), 'restore_verified': False}
        summary[name] = value
(DOC / 'AUDIT_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(dict(counts)))
