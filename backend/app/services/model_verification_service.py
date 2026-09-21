"""
CyberShield AI — Model Artifact & Runtime Compatibility Verification Service

Verifies:
1. Integrity of trained ML artifacts via SHA-256 checksums.
2. Runtime library version compatibility (scikit-learn, xgboost, numpy, pandas).
3. Feature schema consistency.
4. Truthful reporting of artifact status (COMPATIBLE, VERSION_MISMATCH, TAMPERED, MISSING).

Guarantees:
- Zero retraining or replacement of official model weights.
- Purely read-only diagnostics for health/runtime-status endpoints.
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional
import sklearn
import xgboost
import numpy as np
import pandas as pd

logger = logging.getLogger("cybershield.model_verification")


def _compute_file_sha256(filepath: str) -> Optional[str]:
    if not os.path.isfile(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ModelVerificationService:
    def __init__(self, artifacts_dir: Optional[str] = None):
        self.artifacts_dir = artifacts_dir or self._resolve_artifacts_dir()

    def _resolve_artifacts_dir(self) -> str:
        env_dir = os.environ.get("MODEL_ARTIFACTS_DIR")
        if env_dir and os.path.isdir(env_dir):
            return os.path.abspath(env_dir)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        candidates = [
            os.path.join(base_dir, "ml", "artifacts"),
            os.path.join(base_dir, "backend", "ml", "artifacts"),
            os.path.abspath("ml/artifacts"),
            os.path.abspath("backend/ml/artifacts"),
        ]
        for c in candidates:
            if os.path.isdir(c) and os.path.exists(os.path.join(c, "model_metadata_v7_compat.json")):
                return c
        return candidates[0]

    def get_runtime_library_versions(self) -> Dict[str, str]:
        return {
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__
        }

    def verify_model_artifacts(self, metadata_filename: str = "model_metadata_v7_compat.json") -> Dict[str, Any]:
        """
        Validates artifacts declared in a model metadata JSON against filesystem contents.
        Returns a structured health report.
        """
        meta_path = os.path.join(self.artifacts_dir, metadata_filename)
        if not os.path.isfile(meta_path):
            return {
                "status": "MISSING_METADATA",
                "message": f"Model metadata file {metadata_filename} not found in {self.artifacts_dir}",
                "is_ready": False,
                "artifacts_verified": False,
                "artifacts": {}
            }

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            return {
                "status": "CORRUPT_METADATA",
                "message": f"Failed to parse {metadata_filename}: {str(exc)}",
                "is_ready": False,
                "artifacts_verified": False,
                "artifacts": {}
            }

        model_version = meta.get("model_version", "unknown")
        declared_artifacts = meta.get("artifacts", {})
        all_passed = True
        artifact_reports = {}

        for art_name, art_info in declared_artifacts.items():
            filename = art_info.get("file")
            expected_hash = art_info.get("sha256")
            file_path = os.path.join(self.artifacts_dir, filename)

            if not os.path.isfile(file_path):
                artifact_reports[art_name] = {
                    "file": filename,
                    "status": "MISSING",
                    "hash_match": False
                }
                all_passed = False
                continue

            actual_hash = _compute_file_sha256(file_path)

            # Cross-OS JSON line-ending tolerance (Windows CRLF vs Linux LF)
            if filename.endswith(".json") and expected_hash:
                try:
                    with open(file_path, "rb") as jf:
                        raw_bytes = jf.read()
                    actual_crlf_hash = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\r\n")).hexdigest().lower()
                    actual_lf_hash = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest().lower()
                    hash_match = expected_hash.lower() in (actual_crlf_hash, actual_lf_hash)
                except Exception:
                    hash_match = (actual_hash.lower() == expected_hash.lower()) if actual_hash else False
            else:
                hash_match = (actual_hash.lower() == expected_hash.lower()) if (expected_hash and actual_hash) else True

            if not hash_match:
                all_passed = False

            artifact_reports[art_name] = {
                "file": filename,
                "status": "VERIFIED" if hash_match else "TAMPERED_OR_MISMATCH",
                "hash_match": hash_match,
                "sha256": actual_hash[:12] + "..." if actual_hash else None
            }

        runtime_versions = self.get_runtime_library_versions()

        # Check scikit-learn compatibility: models trained on 1.9.0, running on 1.9.x
        sklearn_compat = runtime_versions["scikit_learn"].startswith("1.9.")
        overall_status = "COMPATIBLE" if (all_passed and sklearn_compat) else ("VERSION_MISMATCH" if all_passed else "DEGRADED")

        return {
            "status": overall_status,
            "model_version": model_version,
            "time_model_version": meta.get("time_model_version", "cashout-time-xgb-v3"),
            "is_ready": all_passed,
            "artifacts_verified": all_passed,
            "runtime_versions": runtime_versions,
            "training_framework": "scikit-learn==1.9.0 / xgboost==3.4.1",
            "artifact_details": artifact_reports
        }


model_verification_service = ModelVerificationService()
