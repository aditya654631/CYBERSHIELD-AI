"""
CyberShield AI — Phase 6: Tamper-Evident Evidence Storage & Lifecycle Service.
Provides secure storage abstraction, SHA-256 verification, path-traversal prevention,
atomic streaming upload cleanup, versioned replacement, and malware scanning hooks.
"""

import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, BinaryIO, List
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.models import EvidenceFile, Complaint, User
from backend.app.services.audit_service import log_audit


# Storage root directory configuration
def get_evidence_storage_dir() -> str:
    storage_dir = os.environ.get(
        "EVIDENCE_STORAGE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "evidence")
    )
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


# Security Constants
MAX_EVIDENCE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".csv", ".json", ".txt", ".xlsx", ".docx"
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/csv",
    "application/json",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # Checked against extension whitelist
}

FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".py", ".js", ".dll",
    ".so", ".vbs", ".php", ".scr", ".jar", ".elf", ".msi", ".com",
    ".c", ".cpp", ".vbe", ".jse", ".wsf", ".wsh"
}


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitizes user-provided filename to completely block directory traversal,
    null bytes, and dangerous control characters.
    """
    if not filename:
        return "unnamed_evidence"
    
    # Block path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: Path traversal, path separators, and null bytes are strictly forbidden."
        )

    # Base sanitization: extract basename and strip control characters
    base = os.path.basename(filename).strip()
    clean = re.sub(r'[^\w\.\-\s]', '_', base).strip()
    if not clean or clean.startswith("."):
        clean = "evidence_" + clean.lstrip(".")
    return clean[:255]


def validate_file_type(filename: str, content_type: Optional[str]) -> Tuple[str, str]:
    """
    Validates file extension and MIME type against allowed whitelists.
    Returns (clean_ext, resolved_mime).
    """
    _, ext = os.path.splitext(filename.lower())
    
    if not ext or ext in FORBIDDEN_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Forbidden file type '{ext}'. Executable or script files are strictly prohibited."
        )

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Permitted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    # Resolve/normalize MIME
    mime = (content_type or "").lower().split(";")[0].strip()
    if not mime or mime not in ALLOWED_MIME_TYPES:
        # Fallback mapping based on validated extension
        ext_mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".csv": "text/csv",
            ".json": "application/json",
            ".txt": "text/plain",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime = ext_mime_map.get(ext, "application/octet-stream")

    return ext, mime


def store_file_stream(
    file_stream: BinaryIO,
    original_filename: str,
    max_bytes: int = MAX_EVIDENCE_SIZE_BYTES
) -> Tuple[str, str, int, str]:
    """
    Streams file upload into a temporary file, computes SHA-256 on the fly,
    enforces maximum size limit, and atomically moves to final storage key.
    
    Returns (storage_key, absolute_path, size_bytes, sha256_hash).
    """
    storage_root = get_evidence_storage_dir()
    clean_filename = sanitize_filename(original_filename)
    _, ext = os.path.splitext(clean_filename.lower())
    
    unique_id = uuid.uuid4().hex
    temp_filename = f"tmp_{unique_id}.part"
    temp_path = os.path.join(storage_root, temp_filename)
    
    storage_key = f"evidence/{unique_id}{ext}"
    final_path = os.path.join(storage_root, f"{unique_id}{ext}")

    sha256 = hashlib.sha256()
    size_bytes = 0

    try:
        with open(temp_path, "wb") as f_out:
            while True:
                chunk = file_stream.read(64 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB."
                    )
                sha256.update(chunk)
                f_out.write(chunk)

        if size_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        # Atomic move to final path
        os.replace(temp_path, final_path)
    except Exception:
        # Incomplete upload cleanup
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise

    return storage_key, final_path, size_bytes, sha256.hexdigest()


def get_absolute_file_path(storage_key: str) -> str:
    """Resolves relative storage_key to absolute local file system path."""
    storage_root = get_evidence_storage_dir()
    # Strip prefix e.g. "evidence/"
    rel_key = storage_key.replace("evidence/", "").replace("evidence\\", "")
    # Check for path traversal in stored key as well
    if ".." in rel_key or "/" in rel_key or "\\" in rel_key:
        raise ValueError("Invalid storage key detected.")
    return os.path.join(storage_root, rel_key)


def compute_file_sha256(file_path: str) -> str:
    """Computes cryptographic SHA-256 hash of on-disk file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Evidence file not found on disk at {file_path}")
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_evidence_integrity(evidence: EvidenceFile, db: Session, user: Optional[User] = None) -> Dict[str, Any]:
    """
    Recomputes SHA-256 hash of on-disk file and verifies against stored database hash.
    Detects any tampering or disk corruption.
    """
    file_path = get_absolute_file_path(evidence.storage_key)
    if not os.path.exists(file_path):
        return {
            "evidence_id": evidence.id,
            "status": "FILE_MISSING",
            "is_valid": False,
            "error": "Evidence file is missing on storage system."
        }

    computed_hash = compute_file_sha256(file_path)
    is_valid = (computed_hash == evidence.sha256_hash)

    if not is_valid:
        # Log critical security tamper audit event
        log_audit(
            db=db,
            user_id=user.id if user else None,
            officer_name=user.full_name if user else "SYSTEM_INTEGRITY_CHECK",
            role=user.role if user else "SYSTEM",
            action="EVIDENCE_TAMPER_DETECTED",
            case_number=evidence.complaint.complaint_number if evidence.complaint else None,
            details=f"INTEGRITY VIOLATION: Evidence #{evidence.id} ({evidence.original_filename}) hash mismatch. Stored: {evidence.sha256_hash}, Disk: {computed_hash}."
        )

    return {
        "evidence_id": evidence.id,
        "is_valid": is_valid,
        "stored_hash": evidence.sha256_hash,
        "computed_hash": computed_hash,
        "size_bytes": evidence.size_bytes,
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


def upload_evidence(
    db: Session,
    complaint_id: int,
    file: UploadFile,
    source: str = "OFFICER_UPLOAD",
    description: Optional[str] = None,
    current_user: Optional[User] = None
) -> EvidenceFile:
    """
    Validates and stores a new evidence file for a complaint.
    """
    clean_filename = sanitize_filename(file.filename)
    ext, mime_type = validate_file_type(clean_filename, file.content_type)
    
    storage_key, file_path, size_bytes, sha256_hash = store_file_stream(
        file.file, clean_filename
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    evidence = EvidenceFile(
        complaint_id=complaint_id,
        source=source or "OFFICER_UPLOAD",
        uploader_user_id=current_user.id if current_user else None,
        uploader_role=current_user.role if current_user else "SYSTEM",
        uploader_org_id=current_user.organization_id if current_user else None,
        original_filename=clean_filename,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256_hash=sha256_hash,
        version=1,
        status="ACTIVE",
        malware_scan_status="PENDING_SCAN",
        malware_scan_details="Awaiting background antivirus / malware scan inspection (Local ClamAV / sandbox not configured).",
        description=description,
        created_at=now,
        updated_at=now,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Audit log
    if current_user:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        log_audit(
            db=db,
            user_id=current_user.id,
            officer_name=current_user.full_name,
            role=current_user.role,
            action="EVIDENCE_UPLOADED",
            case_number=complaint.complaint_number if complaint else str(complaint_id),
            details=f"Uploaded evidence file '{clean_filename}' ({size_bytes:,} bytes, SHA-256: {sha256_hash[:12]}...) under Case #{complaint_id}."
        )

    return evidence


def replace_evidence(
    db: Session,
    existing_evidence_id: int,
    file: UploadFile,
    description: Optional[str] = None,
    current_user: Optional[User] = None
) -> EvidenceFile:
    """
    Replaces existing evidence with a new version (v+1).
    Preserves the original evidence record as SUPERSEDED and creates a new ACTIVE record.
    """
    old_evidence = db.query(EvidenceFile).filter(EvidenceFile.id == existing_evidence_id).first()
    if not old_evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    clean_filename = sanitize_filename(file.filename)
    ext, mime_type = validate_file_type(clean_filename, file.content_type)
    
    storage_key, file_path, size_bytes, sha256_hash = store_file_stream(
        file.file, clean_filename
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new_version = (old_evidence.version or 1) + 1

    new_evidence = EvidenceFile(
        complaint_id=old_evidence.complaint_id,
        source=old_evidence.source,
        uploader_user_id=current_user.id if current_user else None,
        uploader_role=current_user.role if current_user else "SYSTEM",
        uploader_org_id=current_user.organization_id if current_user else None,
        original_filename=clean_filename,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256_hash=sha256_hash,
        version=new_version,
        status="ACTIVE",
        malware_scan_status="PENDING_SCAN",
        malware_scan_details="Awaiting background antivirus / malware scan inspection (Local ClamAV / sandbox not configured).",
        description=description or f"Replacement for version {old_evidence.version} ({old_evidence.original_filename})",
        created_at=now,
        updated_at=now,
    )
    db.add(new_evidence)
    db.flush()

    # Mark old evidence as SUPERSEDED
    old_evidence.status = "SUPERSEDED"
    old_evidence.superseded_by_evidence_id = new_evidence.id
    old_evidence.superseded_at = now
    old_evidence.updated_at = now

    db.commit()
    db.refresh(new_evidence)

    # Audit log
    if current_user:
        complaint = db.query(Complaint).filter(Complaint.id == old_evidence.complaint_id).first()
        log_audit(
            db=db,
            user_id=current_user.id,
            officer_name=current_user.full_name,
            role=current_user.role,
            action="EVIDENCE_REPLACED",
            case_number=complaint.complaint_number if complaint else str(old_evidence.complaint_id),
            details=f"Replaced evidence #{old_evidence.id} (v{old_evidence.version}) with new version #{new_evidence.id} (v{new_version}) '{clean_filename}'."
        )

    return new_evidence


def update_malware_scan(
    db: Session,
    evidence_id: int,
    status_val: str,
    details: Optional[str] = None,
    current_user: Optional[User] = None
) -> EvidenceFile:
    """
    Updates honest malware scanning status for an evidence file.
    Permitted states: PENDING_SCAN, QUARANTINED, FAILED_SCAN, UNSCANNED, CLEAN.
    """
    valid_statuses = {"PENDING_SCAN", "QUARANTINED", "FAILED_SCAN", "UNSCANNED", "CLEAN"}
    if status_val.upper() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scan status. Must be one of: {', '.join(sorted(valid_statuses))}."
        )

    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    evidence.malware_scan_status = status_val.upper()
    evidence.malware_scan_details = details
    evidence.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(evidence)
    return evidence
