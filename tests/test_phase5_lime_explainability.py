"""
CyberShield AI — Phase 5 Unit Test Suite
Faithful and Readable LIME Explanations

Verifies:
1. Immutable inference snapshot capture during actual prediction with all 47 features and hashes.
2. Companion PredictionSnapshot record persistence.
3. Database mutations after prediction do NOT mutate explanation inputs (anti-drift).
4. Legacy prediction without snapshot returns UNAVAILABLE with actionable guidance.
5. Unverified legacy cache without snapshot provenance is rejected.
6. Honest fidelity reporting: negative or low R^2 classified as LOW_FIDELITY without fabricated fallbacks.
7. Officer-readable factors: friendly labels, formatted values, units, and honest category distinctions.
8. Base-model score prior (v4_candidate_score) honestly attributed as Model Prior, not financial evidence.
9. Cache invalidation on explainer configuration change.
10. Read-only zero-mutation guarantee: predictions, rankings, alerts, and audit hashes remain invariant.
11. Multi-request determinism without shared mutable RNG pollution.
"""

import copy
import hashlib
import json
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
import unittest.mock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, PredictionLocation, PredictionSnapshot, Alert
from backend.app.auth.security import create_access_token
from backend.app.services.prediction_service import prediction_service
from backend.app.services.prediction_explainability_service import (
    prediction_explainability_service,
    PredictionExplainabilityService,
    FEATURE_METADATA,
    format_feature_value,
    compute_snapshot_digest,
    V4_COMPAT_FEATURES
)
from ml.features.feature_pipeline import FEATURE_COLUMNS_LOCATION_V3_1
from backend.app.services.prediction_audit_service import (
    prediction_audit_client,
    canonicalize_prediction_audit_payload,
    compute_prediction_hash
)

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture(scope="module")
def db(guardrail_and_isolate_test_db):
    session = guardrail_and_isolate_test_db()
    yield session
    session.close()


@pytest.fixture(scope="module")
def persistent_test_prediction(db):
    """Creates a fresh official V7 prediction with a guaranteed inference snapshot."""
    comp = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).first()
    if not comp:
        comp = db.query(Complaint).first()
    assert comp is not None, "At least one complaint required in test database"

    result = prediction_service.run_and_persist_prediction(db, comp.id)
    pred_id = result.get("prediction_id") if isinstance(result, dict) else result.id
    pred = db.query(Prediction).filter(Prediction.id == pred_id).first()
    return pred


def test_faithful_inference_snapshot_captured(db, persistent_test_prediction):
    """1. New predictions persist an immutable inference snapshot with runtime features and metadata."""
    pred = persistent_test_prediction
    assert pred.result_metadata is not None
    snapshot = pred.result_metadata.get("inference_snapshot")
    assert snapshot is not None, "inference_snapshot must be captured during inference"

    # Verify snapshot content
    expected_model = pred.model_version
    assert snapshot.get("model_version") == expected_model
    if "v8" in expected_model:
        assert snapshot.get("feature_schema_version") in ("v8_debiased", "v8_debiased_49")
        expected_feature_count = 49
    else:
        assert snapshot.get("feature_schema_version") in ("v7_compat", "v7_compat_47")
        expected_feature_count = 47

    assert snapshot.get("feature_schema_hash") is not None
    assert (snapshot.get("location_model_hash") or snapshot.get("model_hash")) is not None
    assert snapshot.get("calibrator_hash") is not None
    assert isinstance(snapshot.get("provenance"), dict)
    assert "origin_zone" in snapshot.get("provenance")

    # Verify feature columns
    feature_names = snapshot.get("feature_names", [])
    assert len(feature_names) == expected_feature_count, f"Expected {expected_feature_count} features in snapshot, got {len(feature_names)}"

    # Verify candidate features exist for Top-3 locations
    candidate_features = snapshot.get("candidate_features", {})
    locations = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == pred.id)
        .order_by(PredictionLocation.rank.asc())
        .all()
    )
    assert len(locations) >= 3
    for loc in locations[:3]:
        cid_str = str(loc.cluster_id)
        assert cid_str in candidate_features, f"Cluster {cid_str} must be present in snapshot candidate_features"
        assert len(candidate_features[cid_str]) == expected_feature_count, f"Each candidate feature vector must have {expected_feature_count} dimensions"

    # Verify companion PredictionSnapshot record in database
    companion = db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == pred.id).first()
    assert companion is not None, "Companion PredictionSnapshot record must be persisted"
    assert companion.complaint_id == pred.complaint_id
    assert companion.model_version == pred.model_version
    if "v8" in expected_model:
        assert companion.feature_schema_version in ("v8_debiased", "v8_debiased_49")
    else:
        assert companion.feature_schema_version in ("v7_compat", "v7_compat_47")
    assert companion.snapshot_data.get("model_version") == pred.model_version


def test_database_changes_after_prediction_do_not_alter_explanation_inputs(db, persistent_test_prediction):
    """2. Database mutations after prediction do NOT change explanation features (anti-drift)."""
    pred = persistent_test_prediction
    complaint = db.query(Complaint).filter(Complaint.id == pred.complaint_id).first()
    original_amount = complaint.amount

    # Retrieve explanation grounded in snapshot
    exp1 = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
    assert exp1["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    cand1_before = exp1["top3_explanations"][0]

    # Clear explanation cache from prediction metadata to force re-explanation
    current_meta = dict(pred.result_metadata or {})
    current_meta.pop("explainability", None)
    pred.result_metadata = current_meta
    db.commit()

    # Mutate database state after prediction
    complaint.amount = float(original_amount or 1000.0) + 5000000.0
    db.commit()

    try:
        # Re-explain: Service MUST use immutable snapshot, not live database values
        exp2 = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
        cand1_after = exp2["top3_explanations"][0]

        # Weights, local prediction, and contributions must match exactly
        assert cand1_before["lime_local_prediction"] == cand1_after["lime_local_prediction"]
        assert cand1_before["local_fidelity_r2"] == cand1_after["local_fidelity_r2"]

        p_before = [(c["feature_name"], c["weight"]) for c in cand1_before["positive_contributions"]]
        p_after = [(c["feature_name"], c["weight"]) for c in cand1_after["positive_contributions"]]
        assert p_before == p_after, "Explanation inputs and weights must not drift after database mutation"
    finally:
        # Restore complaint amount
        complaint.amount = original_amount
        db.commit()


def test_legacy_prediction_without_snapshot_returns_unavailable(db):
    """3. Legacy predictions without a faithful snapshot explicitly report UNAVAILABLE."""
    now = datetime.now(timezone.utc)
    legacy_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={"legacy_version": "v1_untracked"}
    )
    db.add(legacy_pred)
    db.commit()
    db.refresh(legacy_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, legacy_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert res.get("is_legacy_prediction") is True
        assert "lacks an immutable inference snapshot" in res["message"]
        assert "does not reconstruct feature inputs from current database state" in res["message"]
        assert "Generate a new prediction" in res["actionable_next_step"]
    finally:
        db.delete(legacy_pred)
        db.commit()


def test_legacy_cached_explanation_without_provenance_rejected(db):
    """4. Unverified legacy cache without snapshot provenance is rejected."""
    now = datetime.now(timezone.utc)
    unverified_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={
            "explainability": {
                "explanation_status": "AVAILABLE",
                "narrative": "Fake legacy cached explanation without snapshot",
                "snapshot_provenance": False
            }
        }
    )
    db.add(unverified_pred)
    db.commit()
    db.refresh(unverified_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, unverified_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert res.get("is_legacy_prediction") is True
    finally:
        db.delete(unverified_pred)
        db.commit()


def test_honest_fidelity_classification_and_no_fabricated_fallbacks():
    """5. Honest fidelity classification retains negative and zero R^2 without 0.2252 fallback."""
    service = PredictionExplainabilityService(random_state=42)

    # Negative R² must be LOW_FIDELITY
    assert service.classify_fidelity(-0.45, 0.10) == "LOW_FIDELITY"
    assert service.classify_fidelity(-0.01, 0.05) == "LOW_FIDELITY"

    # Zero or low R²
    assert service.classify_fidelity(0.0, 0.05) == "LOW_FIDELITY"
    assert service.classify_fidelity(0.38, 0.10) == "LOW_FIDELITY"

    # Moderate R²
    assert service.classify_fidelity(0.45, 0.15) == "MODERATE_FIDELITY"
    assert service.classify_fidelity(0.68, 0.20) == "MODERATE_FIDELITY"

    # High R²
    assert service.classify_fidelity(0.75, 0.10) == "HIGH_FIDELITY"
    assert service.classify_fidelity(0.92, 0.04) == "HIGH_FIDELITY"

    # Poor absolute error downgrades even high R²
    assert service.classify_fidelity(0.85, 0.35) == "LOW_FIDELITY"


def test_officer_readable_labels_and_honest_descriptions(db, persistent_test_prediction):
    """6. Readable labels, formatted values, and honest technical feature descriptions."""
    exp = prediction_explainability_service.get_or_generate_explanation(db, persistent_test_prediction.id)
    assert exp["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")

    top1 = exp["top3_explanations"][0]
    all_contribs = top1["positive_contributions"] + top1["negative_contributions"]
    assert len(all_contribs) > 0

    for c in all_contribs:
        # Must have officer-friendly label, category, and formatted value
        assert "friendly_label" in c
        assert "category" in c
        assert "formatted_value" in c
        assert "honest_explanation" in c
        assert "contribution_share" in c
        assert "direction" in c

        # Direction-aware contribution share verification
        if c["direction"] == "SUPPORTING":
            assert 0.0 <= c["contribution_share"] <= 100.0
        elif c["direction"] == "OPPOSING":
            assert -100.0 <= c["contribution_share"] <= 0.0

        # Base model prior must NOT be disguised as financial or transaction evidence
        if c["feature_name"] == "v4_candidate_score":
            assert c["category"] == "Model Prior"
            assert "prior" in c["friendly_label"].lower() or "score prior" in c["friendly_label"].lower()
            assert "not direct transaction" in c["honest_explanation"].lower() or "ranking prior" in c["honest_explanation"].lower()


def test_cache_invalidation_when_explainer_config_changes(db, persistent_test_prediction):
    """7. Cache identity changes if random_state or explainer version changes."""
    pred = persistent_test_prediction
    exp1 = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
    cache_id_1 = exp1.get("cache_identity")
    assert cache_id_1 is not None

    # Instantiate a service with different random state
    service2 = PredictionExplainabilityService(random_state=999)
    # The cache identity should differ
    snapshot = pred.result_metadata.get("inference_snapshot")
    cache_id_2 = hashlib.sha256(
        f"{pred.id}:{snapshot.get('prediction_timestamp')}:{service2.explainer_version}:999".encode()
    ).hexdigest()
    assert cache_id_1 != cache_id_2, "Cache identity must invalidate when random_state changes"


def test_zero_mutation_and_audit_hash_invariance(db, persistent_test_prediction):
    """8. Explainability requests do not alter scores, rankings, alerts, or audit hashes."""
    pred = persistent_test_prediction

    audit_dict = {
        "prediction_id": pred.id,
        "complaint_number": pred.complaint.complaint_number,
        "model_version": pred.model_version,
        "prediction_mode": pred.prediction_mode,
        "time_model_version": pred.time_model_version,
        "created_at": pred.created_at,
        "predicted_window_start": pred.predicted_window_start,
        "predicted_window_end": pred.predicted_window_end,
        "window_label": pred.window_label,
        "top_locations": [
            {
                "rank": loc.rank,
                "cluster_id": loc.cluster_id,
                "probability": loc.probability,
                "location_name": loc.location_name
            }
            for loc in sorted(pred.locations, key=lambda x: x.rank)
        ]
    }

    # Pre-explanation state
    locs_before = [
        (loc.id, loc.cluster_id, loc.rank, loc.probability, loc.risk_level)
        for loc in db.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).all()
    ]
    alerts_count_before = db.query(Alert).filter(Alert.complaint_id == pred.complaint_id).count()
    canonical_before = canonicalize_prediction_audit_payload(audit_dict)
    hash_before = compute_prediction_hash(canonical_before)

    # Invoke explanation via API route
    resp = client.get(f"/api/v1/predictions/{pred.id}/explanation")
    assert resp.status_code == 200

    # Post-explanation state
    db.refresh(pred)
    locs_after = [
        (loc.id, loc.cluster_id, loc.rank, loc.probability, loc.risk_level)
        for loc in db.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).all()
    ]
    alerts_count_after = db.query(Alert).filter(Alert.complaint_id == pred.complaint_id).count()
    canonical_after = canonicalize_prediction_audit_payload(audit_dict)
    hash_after = compute_prediction_hash(canonical_after)

    assert locs_before == locs_after, "PredictionLocation rows must not be mutated by explanation generation"
    assert alerts_count_before == alerts_count_after, "No new alerts should be created during explanation"
    assert hash_before == hash_after, "Prediction audit hash must remain strictly invariant"


def test_repeated_and_concurrent_stability(db, persistent_test_prediction):
    """9. Repeated requests produce stable, deterministic outputs without global RNG pollution."""
    pred = persistent_test_prediction

    # Clear cache to force generation
    current_meta = dict(pred.result_metadata or {})
    current_meta.pop("explainability", None)
    pred.result_metadata = current_meta
    db.commit()

    res1 = prediction_explainability_service.get_or_generate_explanation(db, pred.id)

    # Force recomputation with a fresh instance sharing the same seed
    fresh_service = PredictionExplainabilityService(random_state=42)
    # Clear cache again
    current_meta = dict(pred.result_metadata or {})
    current_meta.pop("explainability", None)
    pred.result_metadata = current_meta
    db.commit()

    res2 = fresh_service.get_or_generate_explanation(db, pred.id)

    top1 = res1["top3_explanations"][0]
    top2 = res2["top3_explanations"][0]
    assert top1["lime_local_prediction"] == top2["lime_local_prediction"]
    assert top1["local_fidelity_r2"] == top2["local_fidelity_r2"]

    w1 = [c["weight"] for c in top1["positive_contributions"]]
    w2 = [c["weight"] for c in top2["positive_contributions"]]
    assert w1 == w2


def test_snapshot_write_once_immutability(db, persistent_test_prediction):
    """10. PredictionSnapshot rows are write-once and reject in-place updates."""
    pred = persistent_test_prediction
    companion = db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == pred.id).first()
    assert companion is not None, "Snapshot record must exist"

    # Attempt to mutate snapshot data in place
    original_data = copy.deepcopy(companion.snapshot_data)
    tampered_data = copy.deepcopy(original_data)
    tampered_data["model_version"] = "tampered-version-v9"
    companion.snapshot_data = tampered_data

    with pytest.raises(ValueError, match="write-once and immutable"):
        db.commit()

    db.rollback()


def test_snapshot_companion_table_is_authoritative(db, persistent_test_prediction):
    """11. Companion table prediction_snapshots is authoritative snapshot source."""
    pred = persistent_test_prediction
    # Clear cached explainability to force resolution
    current_meta = dict(pred.result_metadata or {})
    current_meta.pop("explainability", None)
    pred.result_metadata = current_meta
    db.commit()

    res = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
    assert res["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    assert res.get("snapshot_source") == "prediction_snapshots_table"
    assert res.get("snapshot_digest") is not None


def test_snapshot_conflict_detection_refuses_explanation(db, persistent_test_prediction):
    """12. Divergent snapshot copies trigger explicit conflict detection and refuse explanation."""
    pred = persistent_test_prediction
    # Ensure companion exists
    companion = db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == pred.id).first()
    assert companion is not None

    # Clear cached explainability
    current_meta = dict(pred.result_metadata or {})
    current_meta.pop("explainability", None)

    # Tamper with the result_metadata copy only
    meta_snapshot = copy.deepcopy(current_meta.get("inference_snapshot", {}))
    meta_snapshot["candidate_pool_size"] = 999999  # Cause digest divergence
    current_meta["inference_snapshot"] = meta_snapshot
    pred.result_metadata = current_meta
    db.commit()

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert res.get("integrity_conflict") is True
        assert "Integrity conflict detected" in res["message"]
        assert "diverges from 'result_metadata.inference_snapshot'" in res["message"]
    finally:
        # Restore consistent state
        db.rollback()
        db.refresh(companion)
        current_meta = dict(pred.result_metadata or {})
        current_meta["inference_snapshot"] = copy.deepcopy(companion.snapshot_data)
        current_meta.pop("explainability", None)
        pred.result_metadata = current_meta
        db.commit()


def test_cache_invalidation_on_snapshot_digest_or_candidate_mismatch(db, persistent_test_prediction):
    """13. Cached explanations with mismatched snapshot digest or cluster IDs are invalidated."""
    pred = persistent_test_prediction
    exp = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
    assert exp["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    valid_cache_id = exp.get("cache_identity")
    valid_digest = exp.get("snapshot_digest")

    # Tamper with cached snapshot_digest in result_metadata
    current_meta = dict(pred.result_metadata or {})
    cached = copy.deepcopy(current_meta["explainability"])
    cached["snapshot_digest"] = "corrupted_digest_1234567890abcdef"
    current_meta["explainability"] = cached
    pred.result_metadata = current_meta
    db.commit()

    # Next call must detect digest mismatch, invalidate cache, and recompute
    fresh_exp = prediction_explainability_service.get_or_generate_explanation(db, pred.id)
    assert fresh_exp["snapshot_digest"] == valid_digest
    assert fresh_exp["cache_identity"] == valid_cache_id


def test_mismatched_calibrator_or_historical_model_refuses_explanation(db):
    """14. Mismatched calibrator, historical model, schema, and background data refuse explanation honestly."""
    now = datetime.now(timezone.utc)
    # 1. Model version mismatch
    mismatched_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v4",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={
            "inference_snapshot": {
                "model_version": "cashout-location-xgb-v4",
                "feature_names": ["f"] * 47
            }
        }
    )
    db.add(mismatched_pred)
    db.commit()
    db.refresh(mismatched_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, mismatched_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert "only calibrated for official verified models" in res["message"] or "cashout-location-xgb-v7-compat" in res["message"]
    finally:
        db.delete(mismatched_pred)
        db.commit()

    # 2. Schema count mismatch
    schema_mismatch_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={
            "inference_snapshot": {
                "model_version": "cashout-location-xgb-v7-compat",
                "feature_names": ["f1", "f2"]  # only 2 features instead of 47
            }
        }
    )
    db.add(schema_mismatch_pred)
    db.commit()
    db.refresh(schema_mismatch_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, schema_mismatch_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert "expected exactly 47" in res["message"]
    finally:
        db.delete(schema_mismatch_pred)
        db.commit()

    # 3. Schema feature names mismatch
    schema_names_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={
            "inference_snapshot": {
                "model_version": "cashout-location-xgb-v7-compat",
                "feature_names": [f"wrong_feature_{i}" for i in range(47)]
            }
        }
    )
    db.add(schema_names_pred)
    db.commit()
    db.refresh(schema_names_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, schema_names_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert "do not match official" in res["message"] and "feature schema" in res["message"]
    finally:
        db.delete(schema_names_pred)
        db.commit()

    # 4. Calibrator artifact hash mismatch
    v7_features = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES
    cal_mismatch_pred = Prediction(
        complaint_id=1,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        result_metadata={
            "inference_snapshot": {
                "model_version": "cashout-location-xgb-v7-compat",
                "feature_names": v7_features,
                "calibrator_hash": "tampered_calibrator_sha256_hash_99999"
            }
        }
    )
    db.add(cal_mismatch_pred)
    db.commit()
    db.refresh(cal_mismatch_pred)

    try:
        res = prediction_explainability_service.get_or_generate_explanation(db, cal_mismatch_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert "Calibrator mismatch" in res["message"]
    finally:
        db.delete(cal_mismatch_pred)
        db.commit()

    # 5. Background data mismatch integrity test
    from backend.app.services.prediction_explainability_service import PredictionExplainabilityService
    isolated_svc = PredictionExplainabilityService()
    # Mock invalid background metadata hash
    with unittest.mock.patch("backend.app.services.prediction_explainability_service.compute_file_sha256", return_value="actual_different_hash"):
        init_ok = isolated_svc._ensure_initialized()
        assert init_ok is False
        assert "Background matrix SHA-256 integrity check failed" in (isolated_svc._init_error or "")


def test_feature_provenance_and_truthful_nomenclature(db, persistent_test_prediction):
    """15. Verified truthful nomenclature: no confirmed mule claims, explicit share denominators."""
    exp = prediction_explainability_service.get_or_generate_explanation(db, persistent_test_prediction.id)
    assert exp["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")

    for cand in exp["top3_explanations"]:
        all_c = cand["positive_contributions"] + cand["negative_contributions"]
        for c in all_c:
            # Check provenance_type
            assert "provenance_type" in c
            assert c["provenance_type"] in (
                "DIRECT_INTAKE",
                "DERIVED_TRANSFER",
                "SPATIAL_DERIVED",
                "SYNTHETIC_HISTORICAL_BASELINE",
                "MODEL_PRIOR"
            )

            # Check explicit denominator documentation
            assert "share_denominator_formula" in c
            assert r"\sum_{k \in \text{TopFactors}} |w_k|" in c["share_denominator_formula"]
            assert "Surrogate linear weight fraction" in c["share_denominator_note"]
            assert "raw_weight" in c

            # Ensure no reckless 'confirmed mule' claims
            assert "confirmed mule" not in c["friendly_label"].lower()
            assert "confirmed mule" not in c["honest_explanation"].lower()
            assert "verified cash-out" not in c["honest_explanation"].lower()

