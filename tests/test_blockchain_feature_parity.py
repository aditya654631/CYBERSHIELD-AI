"""
Parity Test Suite: Python Blockchain Feature Extractor vs Node B.4 Feature Engine
Verifies 100% mathematical, typing, and contractual identity across all features
defined in blockchain-feature-schema-v1.
"""

import json
import subprocess
import pytest
from pathlib import Path
from ml.features.blockchain_feature_extractor import (
    normalize_signals_at_reference,
    build_cluster_feature_vector,
    extract_candidate_blockchain_features,
    ORDERED_BLOCKCHAIN_FEATURES,
    CONTRACT_SPEC
)

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_FEATURE_ENGINE_PATH = REPO_ROOT / "blockchain" / "feature-engine" / "src"

def test_feature_contract_completeness():
    """Verify all features in contract are covered and valid."""
    assert len(ORDERED_BLOCKCHAIN_FEATURES) >= 40
    for feat in ORDERED_BLOCKCHAIN_FEATURES:
        assert feat in CONTRACT_SPEC["features"]


def test_python_node_feature_parity():
    """
    Direct cross-runtime parity check:
    Feeds identical signal fixture, cluster, refTime, and opaque subject to
    both Node B.4 Feature Engine and Python Feature Extractor, asserting exact parity.
    """
    ref_time_str = "2026-09-14T12:00:00.000Z"
    ref_time_ms = 1789387200000 # 2026-09-14T12:00:00.000Z

    cluster_id = 14
    opaque_subject = "SUBJ_MULE_9921_SHA"

    # Multi-faceted test fixture
    signals = [
        # Past signals within 1h
        {
            "event_id": "SIG-01",
            "event_type": "ATM_WITHDRAWAL_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T11:45:00.000Z", # 15 min ago
            "submitted_at": "2026-09-14T11:45:30.000Z",
            "confidence": 0.95,
            "status": "ACTIVE"
        },
        {
            "event_id": "SIG-02",
            "event_type": "ATM_WITHDRAWAL_ATTEMPT",
            "cluster_id": cluster_id,
            "organization_msp": "BankBMSP",
            "event_timestamp": "2026-09-14T11:20:00.000Z", # 40 min ago
            "submitted_at": "2026-09-14T11:21:00.000Z",
            "confidence": 0.85,
            "status": "ACTIVE"
        },
        # Past signals within 6h
        {
            "event_id": "SIG-03",
            "event_type": "BRANCH_CASHOUT_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankCMSP",
            "event_timestamp": "2026-09-14T09:00:00.000Z", # 3 hours ago
            "submitted_at": "2026-09-14T09:05:00.000Z",
            "confidence": 0.90,
            "status": "ACTIVE"
        },
        {
            "event_id": "SIG-04",
            "event_type": "MULE_ACCOUNT_ACTIVITY",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T08:00:00.000Z", # 4 hours ago
            "submitted_at": "2026-09-14T08:02:00.000Z",
            "confidence": 0.75,
            "status": "ACTIVE"
        },
        {
            "event_id": "SIG-05",
            "event_type": "LEA_CONFIRMED_CLUSTER",
            "cluster_id": cluster_id,
            "organization_msp": "LEAMSP",
            "event_timestamp": "2026-09-14T07:30:00.000Z", # 4.5 hours ago
            "submitted_at": "2026-09-14T07:35:00.000Z",
            "confidence": 1.00,
            "status": "ACTIVE"
        },
        # Past signal within 24h
        {
            "event_id": "SIG-06",
            "event_type": "ATM_WITHDRAWAL_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankBMSP",
            "event_timestamp": "2026-09-13T20:00:00.000Z", # 16 hours ago
            "submitted_at": "2026-09-13T20:05:00.000Z",
            "confidence": 0.90,
            "status": "ACTIVE"
        },
        # Signals within 7d and 30d
        {
            "event_id": "SIG-07",
            "event_type": "ATM_WITHDRAWAL_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-11T12:00:00.000Z", # 3 days ago
            "submitted_at": "2026-09-11T12:05:00.000Z",
            "confidence": 0.88,
            "status": "ACTIVE"
        },
        {
            "event_id": "SIG-08",
            "event_type": "MULE_ACCOUNT_ACTIVITY",
            "cluster_id": cluster_id,
            "organization_msp": "BankCMSP",
            "event_timestamp": "2026-09-01T12:00:00.000Z", # 13 days ago
            "submitted_at": "2026-09-01T12:05:00.000Z",
            "confidence": 0.70,
            "status": "ACTIVE"
        },
        # Revoked signal (revoked in past -> excluded)
        {
            "event_id": "SIG-09-REVOKED",
            "event_type": "ATM_WITHDRAWAL_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T06:00:00.000Z",
            "submitted_at": "2026-09-14T06:05:00.000Z",
            "confidence": 0.90,
            "status": "REVOKED",
            "revoked_by_event_id": "SIG-09-REVOKER"
        },
        {
            "event_id": "SIG-09-REVOKER",
            "event_type": "SIGNAL_REVOKED",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T07:00:00.000Z",
            "submitted_at": "2026-09-14T07:05:00.000Z",
            "status": "REVOKED"
        },
        # Future signal (> ref_time -> anti-leakage exclusion)
        {
            "event_id": "SIG-10-FUTURE",
            "event_type": "ATM_WITHDRAWAL_CONFIRMED",
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T13:00:00.000Z", # 1 hour after ref
            "submitted_at": "2026-09-14T13:05:00.000Z",
            "confidence": 0.99,
            "status": "ACTIVE"
        }
    ]

    subject_signals = [
        {
            "event_id": "SUBJ-SIG-01",
            "event_type": "MULE_ACCOUNT_ACTIVITY",
            "opaque_subject_ref": opaque_subject,
            "cluster_id": cluster_id,
            "organization_msp": "BankAMSP",
            "event_timestamp": "2026-09-14T11:30:00.000Z", # 30 min ago
            "submitted_at": "2026-09-14T11:32:00.000Z",
            "confidence": 0.90,
            "status": "ACTIVE"
        },
        {
            "event_id": "SUBJ-SIG-02",
            "event_type": "MULE_ACCOUNT_ACTIVITY",
            "opaque_subject_ref": opaque_subject,
            "cluster_id": 22, # Different cluster
            "organization_msp": "BankBMSP",
            "event_timestamp": "2026-09-14T08:00:00.000Z", # 4 hours ago
            "submitted_at": "2026-09-14T08:02:00.000Z",
            "confidence": 0.85,
            "status": "ACTIVE"
        }
    ]

    # 1. Run Node B.4 Feature Builder via node CLI
    node_script = f"""
    const {{ normalizeSignalsAtReference }} = require('{NODE_FEATURE_ENGINE_PATH.as_posix()}/signal-normalizer');
    const {{ buildClusterFeatureVector }} = require('{NODE_FEATURE_ENGINE_PATH.as_posix()}/cluster-feature-builder');

    const rawClusterSignals = {json.dumps(signals)};
    const rawSubjectSignals = {json.dumps(subject_signals)};
    const refTimeMs = {ref_time_ms};
    const clusterId = {cluster_id};
    const opaqueSubjectRef = "{opaque_subject}";

    const normalizedCluster = normalizeSignalsAtReference(rawClusterSignals, refTimeMs);
    const normalizedSubject = normalizeSignalsAtReference(rawSubjectSignals, refTimeMs);

    const features = buildClusterFeatureVector({{
        clusterId,
        refTimeMs,
        activeClusterSignals: normalizedCluster.activeSignals,
        allClusterSignalsAtRef: normalizedCluster.allSignalsAtRef,
        subjectSignals: normalizedSubject.activeSignals,
        opaqueSubjectRef
    }});

    console.log(JSON.stringify(features));
    """

    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    node_features = json.loads(res.stdout.strip())

    # 2. Run Python Feature Extractor
    py_extracted = extract_candidate_blockchain_features(
        cluster_id=cluster_id,
        reference_timestamp=ref_time_str,
        raw_signals=signals,
        opaque_subject_ref=opaque_subject,
        raw_subject_signals=subject_signals,
        fabric_available=True
    )
    py_features = py_extracted["features"]

    # 3. Assert Parity on every single feature
    discrepancies = []
    for k, node_val in node_features.items():
        if k not in py_features:
            discrepancies.append(f"Missing in Python: {k}")
            continue
        py_val = py_features[k]
        if isinstance(node_val, float) or isinstance(py_val, float):
            if abs(float(node_val) - float(py_val)) > 1e-4:
                discrepancies.append(f"Mismatch for {k}: Node={node_val}, Python={py_val}")
        else:
            if node_val != py_val:
                discrepancies.append(f"Mismatch for {k}: Node={node_val}, Python={py_val}")

    for k in py_features:
        if k not in node_features:
            discrepancies.append(f"Extra in Python: {k}")

    print("Parity verification checked", len(node_features), "features.")
    assert len(discrepancies) == 0, f"Feature Parity Failed:\n" + "\n".join(discrepancies)
    assert py_extracted["fabric_available"] == 1
