import sys
sys.path.insert(0, '.')
import requests
from datetime import datetime
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, Alert, AuditLog

BASE_URL = 'http://127.0.0.1:8000'

print('==================================================')
print('CYBERSHIELD AI — STEP 14 LIVE E2E VERIFICATION')
print('==================================================')

# 1. Login as controlled test officer (User 1: Dr. Vikramaditya Sen, I4C_ADMIN)
login_resp = requests.post(f'{BASE_URL}/api/v1/auth/login', json={
    'email': 'admin@cybershield.gov.in',
    'password': 'CyberAdmin@2026'
})
print('1. LOGIN STATUS:', login_resp.status_code)
assert login_resp.status_code == 200
login_data = login_resp.json()
token = login_data['access_token']
user = login_data['user']
print(f'   Authenticated Officer: {user["full_name"]} (ID: {user["id"]}, Role: {user["role"]})')

auth_headers = {'Authorization': f'Bearer {token}'}

# 2. Register complaint
ts = int(datetime.utcnow().timestamp())
comp_payload = {
    'victim_name': 'Aarav Malhotra',
    'fraud_type': 'KYC Update Fraud',
    'amount': 68000.0,
    'state': 'Delhi',
    'district': 'South Delhi',
    'locality': 'Hauz Khas',
    'payment_channel': 'IMPS',
    'sender_account_number': 'ACC-99112233',
    'beneficiary_account_number': 'ACC-33221199',
    'transaction_ref': f'TXN-LIVE-{ts}',
    'incident_time': datetime.utcnow().isoformat(),
    'reported_at': datetime.utcnow().isoformat()
}
comp_resp = requests.post(f'{BASE_URL}/api/v1/complaints', json=comp_payload, headers=auth_headers)
print('2. REGISTER COMPLAINT STATUS:', comp_resp.status_code)
assert comp_resp.status_code == 200
comp_data = comp_resp.json()
comp_num = comp_data['complaint_number']
print(f'   Created Complaint Number: {comp_num}')

# 3. Run predictive analysis
pred_resp = requests.post(f'{BASE_URL}/api/v1/predictions/{comp_num}', headers=auth_headers)
print('3. RUN PREDICTIVE ANALYSIS STATUS:', pred_resp.status_code)
assert pred_resp.status_code == 200
pred_data = pred_resp.json()
pred_id = pred_data['prediction_id']
print(f'   Prediction ID: #{pred_id}, Where: {pred_data["where_location"]}, When: {pred_data["when_window"]}, Risk: {pred_data["risk_percentage"]}%, Priority: {pred_data["intervention_priority"]}')

# 4. Create alert
alert_resp = requests.post(f'{BASE_URL}/api/v1/alerts/prediction/{pred_id}', headers=auth_headers)
print('4. CREATE ALERT STATUS:', alert_resp.status_code)
assert alert_resp.status_code == 200
alert_data = alert_resp.json()
alert_id = alert_data['id']
print(f'   Alert ID: #{alert_id}, Location: {alert_data["location_name"]}, Status: {alert_data["status"]}')

# 5. Acknowledge alert
ack_resp = requests.post(f'{BASE_URL}/api/v1/alerts/{alert_id}/acknowledge', json={
    'notes': 'Rapid field unit dispatched from South Delhi Cyber Station'
}, headers=auth_headers)
print('5. ACKNOWLEDGE ALERT STATUS:', ack_resp.status_code)
assert ack_resp.status_code == 200
ack_data = ack_resp.json()
print(f'   Alert Status: {ack_data["status"]}, Acknowledged By: {ack_data["acknowledged_by"]}')

# 6. Verify audit logs for this workflow
audit_resp = requests.get(f'{BASE_URL}/api/v1/audit', headers=auth_headers)
print('6. FETCH AUDIT LOGS STATUS:', audit_resp.status_code)
assert audit_resp.status_code == 200
audits = audit_resp.json()

workflow_audits = [a for a in audits if comp_num in (a.get('case_number') or '') or f'Alert #{alert_id}' in (a.get('details') or '')]
print(f'   Recorded Workflow Audit Events: {len(workflow_audits)}')
for a in workflow_audits:
    print(f'   - Event #{a["id"]}: action={a["action"]}, user_id={a.get("user_id")}, officer="{a["officer_name"]}", role={a["role"]}')
    assert a.get('user_id') == user['id']
    assert a['officer_name'] == user['full_name']

print('   ALL AUDIT EVENTS TIED TO AUTHENTICATED USER!')

# 7. Spoofing test: valid JWT for User 5 (Analyst Pooja Kulkarni) + request body claiming Fake Officer / User ID 7777
login2_resp = requests.post(f'{BASE_URL}/api/v1/auth/login', json={
    'email': 'analyst@cybershield.gov.in',
    'password': 'Analyst@2026'
})
token2 = login2_resp.json()['access_token']
headers2 = {'Authorization': f'Bearer {token2}'}

ts2 = int(datetime.utcnow().timestamp())
spoof_payload = {
    'victim_name': 'Meera Joshi',
    'fraud_type': 'ATM Card Skimming',
    'amount': 31000.0,
    'state': 'Delhi',
    'district': 'New Delhi',
    'locality': 'Connaught Place',
    'payment_channel': 'ATM',
    'sender_account_number': 'ACC-12344321',
    'beneficiary_account_number': 'ACC-43211234',
    'transaction_ref': f'TXN-SPOOF-{ts2}',
    # Spoofed fields in request body
    'user_id': 7777,
    'officer_name': 'Impostor General',
    'role': 'SUPREME_COMMAND',
    'acknowledged_by': 'Fake Acknowledger'
}
spoof_resp = requests.post(f'{BASE_URL}/api/v1/complaints', json=spoof_payload, headers=headers2)
print('7. SPOOFING TEST COMPLAINT REGISTRATION STATUS:', spoof_resp.status_code)
assert spoof_resp.status_code == 200
spoof_comp_num = spoof_resp.json()['complaint_number']

audit_resp2 = requests.get(f'{BASE_URL}/api/v1/audit', headers=headers2)
spoof_audit = next((a for a in audit_resp2.json() if a.get('case_number') == spoof_comp_num and a.get('action') == 'COMPLAINT_CREATED'), None)
print(f'   Spoofed Request Persisted Audit Actor: user_id={spoof_audit.get("user_id")}, officer="{spoof_audit["officer_name"]}", role={spoof_audit["role"]}')
assert spoof_audit.get('user_id') == 5
assert spoof_audit['officer_name'] == 'Pooja Kulkarni'
assert 'Impostor' not in spoof_audit['officer_name']
print('   SPOOFED ACTOR BODY FIELDS COMPLETELY IGNORED; REAL USER 5 PERSISTED!')

# 8. Unauthenticated test: attempt protected POST without token
db = SessionLocal()
comp_count_before = db.query(Complaint).count()
pred_count_before = db.query(Prediction).count()
alert_count_before = db.query(Alert).count()
audit_count_before = db.query(AuditLog).count()
db.close()

unauth_resp = requests.post(f'{BASE_URL}/api/v1/complaints', json={'amount': 50000})
print('8. UNAUTHENTICATED POST STATUS:', unauth_resp.status_code)
assert unauth_resp.status_code == 401

db = SessionLocal()
assert db.query(Complaint).count() == comp_count_before
assert db.query(Prediction).count() == pred_count_before
assert db.query(Alert).count() == alert_count_before
assert db.query(AuditLog).count() == audit_count_before
db.close()

print('   UNAUTHENTICATED ATTEMPT CLEANLY REJECTED WITH HTTP 401!')
print('   DB DELTA = 0, AUDIT DELTA = 0 VERIFIED!')
print('==================================================')
print('LIVE E2E VERIFICATION COMPLETED SUCCESSFULLY!')
print('==================================================')
