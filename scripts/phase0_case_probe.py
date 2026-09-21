"""Run the repository's manual E2E probe ONLY against the isolated test fixture."""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
os.chdir(ROOT)
os.environ.update(ENVIRONMENT='test', DATABASE_URL='sqlite:///:memory:',
                  AUTO_SEED_DEMO_DATA='false', FABRIC_GATEWAY_URL='http://127.0.0.1:1/api/v1')
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT)]
import conftest

fixture = conftest.guardrail_and_isolate_test_db.__wrapped__()
factory = next(fixture)
try:
    from test_final_e2e_fresh_complaint import run_final_e2e_verification
    result = run_final_e2e_verification()
    from backend.app.models.models import Complaint, Prediction, PredictionLocation, Alert
    from backend.app.auth.security import create_access_token
    from fastapi.testclient import TestClient
    with factory() as db:
        prediction = db.query(Prediction).order_by(Prediction.id.desc()).first()
        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).one()
        client = TestClient(conftest.app)
        client.headers['Authorization'] = 'Bearer ' + create_access_token({'sub': 'admin@cybershield.gov.in', 'role': 'I4C_ADMIN'})
        snapshot = {'environment': 'isolated synthetic fixture; NOT live PostgreSQL or browser',
                    'existing_manual_probe_passed': bool(result)}
        for name, url in [('prediction', f'/api/v1/predictions/{complaint.complaint_number}'),
                          ('map', f'/api/v1/risk-map/prediction/{complaint.complaint_number}'),
                          ('graph', f'/api/v1/complaints/{complaint.complaint_number}/graph'),
                          ('lime', f'/api/v1/predictions/{prediction.id}/explanation')]:
            res = client.get(url)
            snapshot[name] = {'status_code': res.status_code, 'body': res.json()}
        (OUT / 'demo_case_snapshot.json').write_text(json.dumps(snapshot, indent=2, default=str), encoding='utf-8')
        # Diagnose stale-result reuse without altering application implementation.
        import copy
        from backend.app.services.prediction_persistence_service import prediction_persistence_service
        changed = copy.deepcopy(snapshot['prediction']['body'])
        old_score = changed['top_locations'][1]['probability']
        changed['top_locations'][1]['probability'] = old_score + 0.005
        returned = prediction_persistence_service.persist_prediction(db, complaint, changed)
        stored = next(loc for loc in returned.locations if loc.rank == 2).probability
        repro = {'scope': 'isolated service-level reproduction',
                 'input_changed_rank2_score': changed['top_locations'][1]['probability'],
                 'old_rank2_score': old_score, 'stored_rank2_score': stored,
                 'old_prediction_id': prediction.id, 'returned_prediction_id': returned.id,
                 'changed_result_reused_old_prediction': returned.id == prediction.id and abs(stored - old_score) < 1e-6}
        (OUT / 'stale_prediction_reproduction.json').write_text(json.dumps(repro, indent=2), encoding='utf-8')
        print('SNAPSHOT_SAVED', flush=True)
finally:
    try:
        next(fixture)
    except StopIteration:
        pass
