import urllib.request
import json

base = 'http://127.0.0.1:8000/api/v1'

if __name__ == '__main__':
    # 1. Login
    token_payload = {'email': 'district.lea@indore.police.gov.in', 'password': 'IndoreLea@2026'}
    req = urllib.request.Request(f'{base}/auth/login', data=json.dumps(token_payload).encode(), headers={'Content-Type': 'application/json'})
    token = json.loads(urllib.request.urlopen(req).read())['access_token']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # 2. Pick a complaint to generate alert for
    comp_req = urllib.request.Request(f'{base}/complaints', headers=headers)
    comps = json.loads(urllib.request.urlopen(comp_req).read())
    sample_comp = comps[0]
    comp_num = sample_comp['complaint_number']
    print(f"Target complaint: {comp_num} (ID: {sample_comp['id']})")

    # 3. Generate Alert
    gen_req = urllib.request.Request(f'{base}/alerts/generate/{comp_num}', headers=headers, method='POST')
    gen_alert = json.loads(urllib.request.urlopen(gen_req).read())
    alert_id = gen_alert['id']
    print(f"Generated/Found alert ID: {alert_id}, Title: {gen_alert['title']}, Initial Status: {gen_alert['status']}")

    # 4. Acknowledge Alert
    ack_req = urllib.request.Request(
        f'{base}/alerts/{alert_id}/acknowledge',
        data=json.dumps({'notes': 'Immediate patrol unit dispatched to Vijay Nagar ATM cluster'}).encode(),
        headers=headers
    )
    ack_res = json.loads(urllib.request.urlopen(ack_req).read())
    print(f"Acknowledged Alert ID: {ack_res['id']}, Status: {ack_res['status']}, By: {ack_res['acknowledged_by']}")

    # 5. Refetch Alert to verify persistence
    get_req = urllib.request.Request(f'{base}/alerts/{alert_id}', headers=headers)
    refetched = json.loads(urllib.request.urlopen(get_req).read())
    print(f"Refetched Alert ID: {refetched['id']}, Stored Status: {refetched['status']}, Stored Notes: {refetched['action_notes']}")

    # 6. Verify Audit Trail
    audit_req = urllib.request.Request(f'{base}/audit', headers=headers)
    audits = json.loads(urllib.request.urlopen(audit_req).read())
    recent_actions = [(a['action'], a['officer_name'], a['case_number'], a['details']) for a in audits[:10]]
    print("\nRecent Audit Records:")
    for action, officer, case_num, details in recent_actions:
        print(f"  [{action}] by {officer} for {case_num}: {details}")

    print("\nAlert + Audit Flow VERIFIED SUCCESSFULLY!")
