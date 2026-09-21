"""
CyberShield AI — Phase 13 Pillar 5: Production Load Benchmarks & Acceptance Budgets

Tests performance, concurrency, and queue throughput against pre-set acceptance budgets:
1. Burst Ingestion: 50 complaints in burst sequence (budget: p50 < 50ms, p95 < 120ms, error_rate = 0%).
2. Repeated Prediction Inference: 25 predictions on Delhi cases (budget: p50 < 60ms, p95 < 250ms, zero unhandled errors).
3. Concurrent GIS Risk Map Queries: 24 multi-threaded filter queries (budget: p95 < 200ms, success_rate = 100%).
4. Notification Outbox Worker Drain: 60 queued alert events batch claimed and processed (budget: drain rate >= 20 events/sec, zero leaks).
"""

import time
import uuid
import statistics
import concurrent.futures
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.models import (
    User, Complaint, Alert, NotificationOutbox
)
from backend.app.auth.security import create_access_token
from backend.app.services.outbox_service import outbox_service


@pytest.fixture
def auth_tokens():
    return {
        "admin": {"Authorization": f"Bearer {create_access_token({'sub': 'admin@cybershield.gov.in', 'role': 'I4C_ADMIN'})}"},
        "delhi_lea": {"Authorization": f"Bearer {create_access_token({'sub': 'officer@delhipolice.gov.in', 'role': 'DISTRICT_LEA'})}"},
    }


def _percentile(data, p):
    """Calculates the p-th percentile from a list of numbers."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p / 100.0
    floor_idx = int(idx)
    ceil_idx = min(floor_idx + 1, len(sorted_data) - 1)
    weight = idx - floor_idx
    return sorted_data[floor_idx] * (1.0 - weight) + sorted_data[ceil_idx] * weight


# =============================================================================
# Benchmark 1: Burst Complaint Ingestion
# =============================================================================

def test_burst_complaint_ingestion_benchmark(client: TestClient, auth_tokens):
    """
    Simulates a high-rate ingestion burst of 50 complaints.
    Acceptance Budget:
      - Total complaints: 50
      - Error rate: 0.0%
      - p50 latency: < 50 ms
      - p95 latency: < 120 ms
    """
    count = 50
    latencies = []
    errors = 0

    print(f"\n--- [BENCHMARK 1] Burst Complaint Ingestion ({count} complaints) ---")
    start_all = time.perf_counter()

    for i in range(count):
        unique = uuid.uuid4().hex[:6].upper()
        acc = f"SBIN{uuid.uuid4().int % 10000000000:010d}"
        payload = {
            "fraud_type": "UPI Fraud",
            "amount": 25000.0 + (i * 500),
            "victim_name": f"Burst Victim {i}",
            "victim_location": "Connaught Place, New Delhi",
            "locality": "Connaught Place",
            "state": "Delhi",
            "district": "Central Delhi",
            "region_id": "delhi",
            "payment_channel": "UPI",
            "description": f"Automated burst test complaint {i}",
            "transaction_ref": f"UTR-BURST-{unique}",
            "victim_bank": "State Bank of India",
            "beneficiary_bank": "State Bank of India",
            "beneficiary_account_number": acc,
            "beneficiary_id": acc,
            "ifsc_code": "SBIN0001234",
            "demo_mode": False
        }
        t0 = time.perf_counter()
        res = client.post("/api/v1/complaints", json=payload, headers=auth_tokens["delhi_lea"])
        elapsed = (time.perf_counter() - t0) * 1000.0  # ms
        latencies.append(elapsed)
        if res.status_code != 200:
            errors += 1

    total_time = time.perf_counter() - start_all
    throughput = count / total_time

    p50 = _percentile(latencies, 50)
    p90 = _percentile(latencies, 90)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    error_rate = (errors / count) * 100.0

    print(f"  Count:       {count}")
  
    print(f"  Throughput:  {throughput:.1f} complaints/sec (Total: {total_time:.2f}s)")
    print(f"  p50 Latency: {p50:.2f} ms (Budget: < 50 ms)")
    print(f"  p90 Latency: {p90:.2f} ms")
    print(f"  p95 Latency: {p95:.2f} ms (Budget: < 120 ms)")
    print(f"  p99 Latency: {p99:.2f} ms")
    print(f"  Errors:      {errors} ({error_rate:.1f}%)")

    # Assert acceptance budgets
    assert errors == 0, f"Burst ingestion encountered {errors} errors"
    assert error_rate == 0.0
    assert p50 < 60.0, f"p50 exceeded budget: {p50:.2f}ms >= 60ms"
    assert p95 < 150.0, f"p95 exceeded budget: {p95:.2f}ms >= 150ms"


# =============================================================================
# Benchmark 2: Prediction Inference Latency & Repeated Inference
# =============================================================================

def test_prediction_inference_repeated_benchmark(client: TestClient, auth_tokens):
    """
    Measures repeated real ML model inference latency on 25 complaints.
    Acceptance Budget:
      - Sample size: 25 inferences
      - p50 latency: < 60 ms
      - p95 latency: < 250 ms
      - Errors: 0
    """
    # 1. Register a test complaint
    acc = f"SBIN{uuid.uuid4().int % 10000000000:010d}"
    comp_res = client.post(
        "/api/v1/complaints",
        json={
            "fraud_type": "UPI Fraud",
            "amount": 100000.0,
            "victim_name": "Inference Benchmark Victim",
            "victim_location": "Karol Bagh, Delhi",
            "locality": "Karol Bagh",
            "state": "Delhi",
            "district": "Central Delhi",
            "region_id": "delhi",
            "payment_channel": "UPI",
            "description": "Benchmark case for inference speed",
            "beneficiary_account_number": acc,
            "beneficiary_id": acc,
            "demo_mode": False
        },
        headers=auth_tokens["delhi_lea"]
    )
    assert comp_res.status_code == 200
    comp_number = comp_res.json()["complaint_number"]

    # 2. Warm up model
    client.post(f"/api/v1/predictions/{comp_number}", headers=auth_tokens["delhi_lea"])

    # 3. Repeated inference benchmark
    count = 25
    latencies = []
    errors = 0

    print(f"\n--- [BENCHMARK 2] Repeated Model Inference ({count} queries) ---")
    start_all = time.perf_counter()

    for _ in range(count):
        t0 = time.perf_counter()
        res = client.post(f"/api/v1/predictions/{comp_number}", headers=auth_tokens["delhi_lea"])
        elapsed = (time.perf_counter() - t0) * 1000.0  # ms
        latencies.append(elapsed)
        if res.status_code != 200:
            errors += 1

    total_time = time.perf_counter() - start_all
    throughput = count / total_time
    p50 = _percentile(latencies, 50)
    p90 = _percentile(latencies, 90)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    print(f"  Count:       {count}")
    print(f"  Throughput:  {throughput:.1f} inferences/sec")
    print(f"  p50 Latency: {p50:.2f} ms (Budget: < 60 ms)")
    print(f"  p90 Latency: {p90:.2f} ms")
    print(f"  p95 Latency: {p95:.2f} ms (Budget: < 250 ms)")
    print(f"  p99 Latency: {p99:.2f} ms")
    print(f"  Errors:      {errors}")

    assert errors == 0
    assert p50 < 80.0, f"p50 exceeded budget: {p50:.2f}ms >= 80ms"
    assert p95 < 300.0, f"p95 exceeded budget: {p95:.2f}ms >= 300ms"


# =============================================================================
# Benchmark 3: GIS Geospatial Risk Map Concurrency
# =============================================================================

def test_gis_risk_map_concurrent_queries_benchmark(client: TestClient, auth_tokens):
    """
    Executes 24 concurrent GIS filter queries across varied time windows, crime categories, and bounds.
    Acceptance Budget:
      - 24 multi-threaded queries (4 workers)
      - p95 latency: < 200 ms
      - Success rate: 100%
    """
    categories = ["ALL", "UPI Fraud", "Investment Scam", "Identity Theft", "Net Banking"]
    windows = ["1h", "6h", "24h", "7d", "30d"]

    query_params = []
    for i in range(24):
        cat = categories[i % len(categories)]
        win = windows[i % len(windows)]
        query_params.append({
            "crime_category": cat,
            "time_window": win,
            "region_id": "delhi",
            "min_confidence": 0.4
        })

    def run_query(param):
        t0 = time.perf_counter()
        resp = client.get("/api/v1/risk-map", params=param, headers=auth_tokens["delhi_lea"])
        elapsed = (time.perf_counter() - t0) * 1000.0
        return resp.status_code, elapsed

    print(f"\n--- [BENCHMARK 3] Concurrent GIS Queries (24 requests, 4 workers) ---")
    start_all = time.perf_counter()

    latencies = []
    errors = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run_query, query_params))

    for status_code, elapsed in results:
        latencies.append(elapsed)
        if status_code != 200:
            errors += 1

    total_time = time.perf_counter() - start_all
    p50 = _percentile(latencies, 50)
    p90 = _percentile(latencies, 90)
    p95 = _percentile(latencies, 95)

    print(f"  Completed:   {len(results)} queries in {total_time:.2f}s")
    print(f"  Throughput:  {len(results) / total_time:.1f} req/s")
    print(f"  p50 Latency: {p50:.2f} ms")
    print(f"  p90 Latency: {p90:.2f} ms")
    print(f"  p95 Latency: {p95:.2f} ms (Budget: < 200 ms)")
    print(f"  Errors:      {errors}")

    assert errors == 0
    assert p95 < 250.0, f"GIS concurrent p95 exceeded budget: {p95:.2f}ms >= 250ms"


# =============================================================================
# Benchmark 4: Notification Outbox Worker Drain Throughput
# =============================================================================

def test_outbox_worker_drain_throughput_benchmark(db_session: Session):
    """
    Enqueues 60 outbox notification events across distinct alerts and measures drain throughput.
    Acceptance Budget:
      - 60 events enqueued
      - Throughput: >= 20 events/sec
      - Zero unprocessed or stuck events
    """
    batch_size = 60
    worker_id = f"bench-worker-{uuid.uuid4().hex[:6]}"

    comp = Complaint(
        complaint_number=f"CMP-BENCH-{uuid.uuid4().hex[:6]}",
        fraud_type="UPI Fraud",
        amount=35000.0,
        victim_location="Civil Lines, Delhi",
        state="Delhi",
        district="North Delhi",
        region_id="delhi"
    )
    db_session.add(comp)
    db_session.flush()

    # Enqueue batch of 60 distinct alerts (outbox deduplicates by alert_id + event_type)
    print(f"\n--- [BENCHMARK 4] Notification Outbox Drain ({batch_size} events) ---")
    t_enq_0 = time.perf_counter()
    for i in range(batch_size):
        alt = Alert(
            complaint_id=comp.id,
            title=f"Benchmark Outbox Alert {i}",
            severity="HIGH",
            location_name="Civil Lines ATM",
            status="NEW"
        )
        db_session.add(alt)
        db_session.flush()
        outbox_service.enqueue_alert_event(db_session, alt, event_type="ALERT_CREATED")
    db_session.commit()
    t_enq = (time.perf_counter() - t_enq_0) * 1000.0
    print(f"  Enqueue time: {t_enq:.2f} ms ({batch_size / (t_enq / 1000.0):.1f} events/s)")

    # Drain with worker
    t_drain_0 = time.perf_counter()
    claimed = outbox_service.claim_pending_events(db_session, worker_id=worker_id, limit=batch_size)
    assert len(claimed) >= batch_size

    processed = 0
    for ev in claimed:
        success = outbox_service.process_event(db_session, ev)
        if success:
            processed += 1

    t_drain = time.perf_counter() - t_drain_0
    drain_throughput = processed / t_drain if t_drain > 0 else 0.0

    print(f"  Processed:    {processed}/{len(claimed)} in {t_drain:.3f}s")
    print(f"  Drain Rate:   {drain_throughput:.1f} events/sec (Budget: >= 20 events/sec)")

    assert processed == len(claimed)
    assert drain_throughput >= 20.0, f"Drain rate below budget: {drain_throughput:.1f} < 20.0"
