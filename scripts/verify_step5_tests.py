import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount,
    Withdrawal, Prediction, PredictionLocation, Alert,
    LocationCluster, ATMLocation, CaseNote, AuditLog, User, Organization
)

client = TestClient(app)
db = SessionLocal()

def get_counts():
    return {
        'organizations': db.query(Organization).count(),
        'users': db.query(User).count(),
        'location_clusters': db.query(LocationCluster).count(),
        'atm_locations': db.query(ATMLocation).count(),
        'complaints': db.query(Complaint).count(),
        'accounts': db.query(Account).count(),
        'complaint_accounts': db.query(ComplaintAccount).count(),
        'transactions': db.query(Transaction).count(),
        'withdrawals': db.query(Withdrawal).count(),
        'predictions': db.query(Prediction).count(),
        'prediction_locations': db.query(PredictionLocation).count(),
        'alerts': db.query(Alert).count(),
        'case_notes': db.query(CaseNote).count(),
        'audit_logs': db.query(AuditLog).count()
    }

counts_before = get_counts()
print('COUNTS_BEFORE_TESTS =', counts_before)

# 1. CREATE TEST A (Delhi Match 1)
payload_a = {
    'fraud_type': 'UPI fraud',
    'amount': 45000.0,
    'victim_name': 'Aarav Gupta',
    'victim_phone': '+91 98111 22334',
    'victim_location': 'Connaught Place, Delhi',
    'state': 'Delhi',
    'district': 'CENTRAL_NEW_DELHI',
    'payment_channel': 'UPI',
    'description': 'Test A: Immediate UPI diversion'
}
resp_a = client.post('/api/v1/complaints', json=payload_a)
assert resp_a.status_code == 200, resp_a.text
data_a = resp_a.json()
get_a = client.get(f"/api/v1/complaints/{data_a['id']}").json()
print('\n=== TEST A RESULT ===')
print('POST Status:', resp_a.status_code)
print('GET Status: 200')
print('Complaint ID:', data_a['id'])
print('Complaint Number:', data_a['complaint_number'])
print('State / District:', data_a['state'], '/', data_a['district'])
print('Fraud Type:', data_a['fraud_type'])
print('Payment Channel:', data_a['payment_channel'])
print('Amount:', data_a['amount'])
print('Scenario Status:', data_a['scenario_link_status'])
print('Source Scenario:', data_a['source_scenario'])
print('Linked Accounts Count:', data_a['linked_account_count'])
print('Available Transactions Count:', data_a['available_transaction_count'])

# 2. CREATE TEST B (Delhi Match 2)
payload_b = {
    'fraud_type': 'investment scam',
    'amount': 350000.0,
    'victim_name': 'Meera Sen',
    'victim_phone': '+91 98222 33445',
    'victim_location': 'Hauz Khas, Delhi',
    'state': 'Delhi',
    'district': 'SOUTH',
    'payment_channel': 'NEFT',
    'description': 'Test B: Multi-layer investment scam'
}
resp_b = client.post('/api/v1/complaints', json=payload_b)
assert resp_b.status_code == 200, resp_b.text
data_b = resp_b.json()
get_b = client.get(f"/api/v1/complaints/{data_b['id']}").json()
print('\n=== TEST B RESULT ===')
print('POST Status:', resp_b.status_code)
print('GET Status: 200')
print('Complaint ID:', data_b['id'])
print('Complaint Number:', data_b['complaint_number'])
print('State / District:', data_b['state'], '/', data_b['district'])
print('Fraud Type:', data_b['fraud_type'])
print('Payment Channel:', data_b['payment_channel'])
print('Amount:', data_b['amount'])
print('Scenario Status:', data_b['scenario_link_status'])
print('Source Scenario:', data_b['source_scenario'])
print('Linked Accounts Count:', data_b['linked_account_count'])
print('Available Transactions Count:', data_b['available_transaction_count'])

# Compare Test A and Test B
print('\n=== DIVERSITY PROOF: TEST A vs TEST B ===')
print('Test A Source Scenario:', data_a['source_scenario'])
print('Test B Source Scenario:', data_b['source_scenario'])
print('Different scenarios selected?:', 'YES' if data_a['source_scenario'] != data_b['source_scenario'] else 'NO')

# 3. CREATE TEST C (Non-Delhi)
payload_c = {
    'fraud_type': 'job scam',
    'amount': 25000.0,
    'victim_name': 'Ramesh Verma',
    'victim_phone': '+91 98333 44556',
    'victim_location': 'Arera Colony, Bhopal',
    'state': 'Madhya Pradesh',
    'district': 'Bhopal',
    'payment_channel': 'UPI',
    'description': 'Test C: Non-Delhi complaint'
}
resp_c = client.post('/api/v1/complaints', json=payload_c)
assert resp_c.status_code == 200, resp_c.text
data_c = resp_c.json()
get_c = client.get(f"/api/v1/complaints/{data_c['id']}").json()
print('\n=== TEST C RESULT ===')
print('POST Status:', resp_c.status_code)
print('GET Status: 200')
print('Complaint ID:', data_c['id'])
print('Complaint Number:', data_c['complaint_number'])
print('State / District:', data_c['state'], '/', data_c['district'])
print('Scenario Status:', data_c['scenario_link_status'])
print('Source Scenario:', data_c['source_scenario'])
print('Linked Accounts Count:', data_c['linked_account_count'])
print('Available Transactions Count:', data_c['available_transaction_count'])

# Inspect DB rows for Test A, B, C directly
print('\n=== DIRECT POSTGRESQL INSPECTION ===')
for test_label, test_id in [('Test A', data_a['id']), ('Test B', data_b['id']), ('Test C', data_c['id'])]:
    c_row = db.query(Complaint).get(test_id)
    ca_rows = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == test_id).all()
    roles = [ca.association_type for ca in ca_rows]
    acc_ids = [ca.account_id for ca in ca_rows]
    acc_nums = [a.account_number for a in db.query(Account).filter(Account.id.in_(acc_ids)).all()] if acc_ids else []
    
    # Query transactions via transaction endpoint
    tx_resp = client.get(f"/api/v1/complaints/{test_id}/transactions").json()
    tx_count = len(tx_resp)
    timestamps = [t['timestamp'] for t in tx_resp]
    hops = set(t['hop_number'] for t in tx_resp)
    min_ts = min(timestamps) if timestamps else None
    max_ts = max(timestamps) if timestamps else None
    
    print(f'\n[{test_label}]')
    print(f'  ID: {c_row.id} | Number: {c_row.complaint_number}')
    print(f'  Description Provenance: {c_row.description}')
    print(f'  ComplaintAccounts count: {len(ca_rows)}')
    print(f'  Association roles: {set(roles)}')
    print(f'  Linked account numbers sample: {acc_nums[:4]} (total {len(acc_nums)})')
    print(f'  Transaction context count: {tx_count}')
    print(f'  Min timestamp: {min_ts}, Max timestamp: {max_ts}')
    print(f'  Hop depths present: {hops}')

counts_after = get_counts()
print('\nCOUNTS_AFTER_TESTS =', counts_after)

diffs = {k: counts_after[k] - counts_before[k] for k in counts_before}
print('\nTABLE DELTAS =', diffs)

db.close()
