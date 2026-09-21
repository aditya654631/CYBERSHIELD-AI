"""CyberShield AI — Geography Catalog and Multi-Region Routing Service.
Phase 12: Configurable Geography & Second-Region Readiness Gate.

Enforces:
  1. Strict catalog record validation: reject bad lat/lon, duplicate identities,
     invalid organization mapping, missing provenance/licence, cross-region leakage.
  2. Decoupling of geography availability from model validity:
     adding coordinates or synthetic fixtures never confers MODEL_SUPPORTED status.
  3. Deterministic multi-region resolution without silent Delhi fallbacks.
  4. Labelled synthetic second-region fixtures (Mumbai MMR) for functional workflow tests.
"""
import re
import math
import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.models import Region, GeographyCatalog, LocationCluster, ATMLocation, Organization, User, Complaint

logger = logging.getLogger("cybershield.geography_catalog_service")

# Territorial Indian bounding box limits
INDIA_LAT_MIN = 6.0
INDIA_LAT_MAX = 38.0
INDIA_LON_MIN = 68.0
INDIA_LON_MAX = 98.0

# Canonical Delhi Districts
DELHI_DISTRICTS = [
    "CENTRAL_NEW_DELHI",
    "SOUTH",
    "SOUTH_EAST",
    "WEST",
    "SOUTH_WEST_DWARKA",
    "NORTH",
    "NORTH_WEST",
    "EAST",
    "NORTH_EAST_SHAHDARA"
]

# Canonical Mumbai Districts (Second Region Test Fixture)
MUMBAI_DISTRICTS = [
    "MUMBAI",
    "MUMBAI_SUBURBAN",
    "THANE",
    "NAVI_MUMBAI"
]

# Synthetic Mumbai MMR Clusters for functional workflow tests
SYNTHETIC_MUMBAI_CLUSTERS = [
    {
        "name": "Bandra Kurla Complex (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "lat": 19.0657,
        "lon": 72.8687,
        "radius": 3.0,
        "fraud_count": 0,
        "risk": 0.50,
        "atm_count": 2,
    },
    {
        "name": "Andheri East Station (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "lat": 19.1197,
        "lon": 72.8464,
        "radius": 2.5,
        "fraud_count": 0,
        "risk": 0.50,
        "atm_count": 2,
    },
    {
        "name": "Colaba Causeway (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "lat": 18.9150,
        "lon": 72.8258,
        "radius": 2.5,
        "fraud_count": 0,
        "risk": 0.45,
        "atm_count": 2,
    },
    {
        "name": "Dadar TT Circle (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "lat": 19.0178,
        "lon": 72.8478,
        "radius": 2.5,
        "fraud_count": 0,
        "risk": 0.55,
        "atm_count": 2,
    },
    {
        "name": "Thane West Station (Synthetic)",
        "city": "Thane",
        "district": "THANE",
        "state": "Maharashtra",
        "lat": 19.1860,
        "lon": 72.9750,
        "radius": 3.0,
        "fraud_count": 0,
        "risk": 0.40,
        "atm_count": 2,
    },
    {
        "name": "Vashi Sector 17 (Synthetic)",
        "city": "Navi Mumbai",
        "district": "NAVI_MUMBAI",
        "state": "Maharashtra",
        "lat": 19.0771,
        "lon": 72.9986,
        "radius": 3.0,
        "fraud_count": 0,
        "risk": 0.45,
        "atm_count": 2,
    },
]

# Synthetic Mumbai ATMs
SYNTHETIC_MUMBAI_ATMS = [
    {
        "atm_code": "ATM-MUM-SYN-001",
        "bank_name": "State Bank of India",
        "address": "BKC G Block, Bandra East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "latitude": 19.0660,
        "longitude": 72.8690,
        "cluster_name": "Bandra Kurla Complex (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-002",
        "bank_name": "HDFC Bank",
        "address": "BKC C-60, Bandra East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "latitude": 19.0650,
        "longitude": 72.8680,
        "cluster_name": "Bandra Kurla Complex (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-003",
        "bank_name": "ICICI Bank",
        "address": "Andheri Kurla Road, Andheri East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "latitude": 19.1200,
        "longitude": 72.8470,
        "cluster_name": "Andheri East Station (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-004",
        "bank_name": "Punjab National Bank",
        "address": "Sahar Road, Andheri East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI_SUBURBAN",
        "state": "Maharashtra",
        "latitude": 19.1190,
        "longitude": 72.8460,
        "cluster_name": "Andheri East Station (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-005",
        "bank_name": "State Bank of India",
        "address": "Shahid Bhagat Singh Rd, Colaba, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "latitude": 18.9155,
        "longitude": 72.8260,
        "cluster_name": "Colaba Causeway (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-006",
        "bank_name": "Bank of Baroda",
        "address": "Colaba Post Office Rd, Colaba, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "latitude": 18.9145,
        "longitude": 72.8250,
        "cluster_name": "Colaba Causeway (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-007",
        "bank_name": "Axis Bank",
        "address": "Dadar TT Circle, Dadar East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "latitude": 19.0180,
        "longitude": 72.8480,
        "cluster_name": "Dadar TT Circle (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-008",
        "bank_name": "Canara Bank",
        "address": "Dr B.A. Road, Dadar East, Mumbai (Synthetic)",
        "city": "Mumbai",
        "district": "MUMBAI",
        "state": "Maharashtra",
        "latitude": 19.0175,
        "longitude": 72.8475,
        "cluster_name": "Dadar TT Circle (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-009",
        "bank_name": "State Bank of India",
        "address": "Station Road, Thane West (Synthetic)",
        "city": "Thane",
        "district": "THANE",
        "state": "Maharashtra",
        "latitude": 19.1865,
        "longitude": 72.9755,
        "cluster_name": "Thane West Station (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-010",
        "bank_name": "Union Bank of India",
        "address": "Gokhale Road, Thane West (Synthetic)",
        "city": "Thane",
        "district": "THANE",
        "state": "Maharashtra",
        "latitude": 19.1855,
        "longitude": 72.9745,
        "cluster_name": "Thane West Station (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-011",
        "bank_name": "HDFC Bank",
        "address": "Sector 17 Market, Vashi, Navi Mumbai (Synthetic)",
        "city": "Navi Mumbai",
        "district": "NAVI_MUMBAI",
        "state": "Maharashtra",
        "latitude": 19.0775,
        "longitude": 72.9990,
        "cluster_name": "Vashi Sector 17 (Synthetic)",
    },
    {
        "atm_code": "ATM-MUM-SYN-012",
        "bank_name": "ICICI Bank",
        "address": "Palm Beach Road, Sector 17, Vashi (Synthetic)",
        "city": "Navi Mumbai",
        "district": "NAVI_MUMBAI",
        "state": "Maharashtra",
        "latitude": 19.0765,
        "longitude": 72.9980,
        "cluster_name": "Vashi Sector 17 (Synthetic)",
    },
]


class GeographyCatalogValidator:
    """
    Validates geography catalog import payloads.
    Guarantees:
      - Coordinate validity within India and regional bounding box.
      - Unique cluster and ATM identities.
      - Explicit source, license, and provenance documentation.
      - Disjoint boundary enforcement to prevent cross-region leakage.
      - Separation of geography availability from model validity.
    """

    @classmethod
    def validate_catalog(cls, payload: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Header Validation
        region_id = str(payload.get("region_id") or payload.get("id") or "").strip().lower()
        if not region_id:
            errors.append("Missing required field: 'region_id'.")
        elif not re.match(r"^[a-z0-9_]{2,50}$", region_id):
            errors.append(f"Invalid 'region_id' format: '{region_id}'. Must be 2-50 lowercase alphanumeric characters or underscores.")

        region_name = str(payload.get("region_name") or payload.get("name") or "").strip()
        if not region_name:
            errors.append("Missing required field: 'region_name'.")

        catalog_version = str(payload.get("catalog_version") or "").strip()
        if not catalog_version:
            errors.append("Missing required field: 'catalog_version'.")

        source = str(payload.get("source") or "").strip()
        if not source:
            errors.append("Missing required provenance field: 'source'. Source agency / authority must be documented.")

        license_str = str(payload.get("license") or "").strip()
        if not license_str:
            errors.append("Missing required licensing field: 'license'. Data licence / terms of use must be documented.")

        # 2. Regional Bounding Box Validation
        bounds = payload.get("bounds") or {}
        try:
            min_lat = float(bounds.get("min_lat"))
            max_lat = float(bounds.get("max_lat"))
            min_lon = float(bounds.get("min_lon"))
            max_lon = float(bounds.get("max_lon"))
        except (TypeError, ValueError):
            errors.append("Invalid or missing 'bounds'. Must specify numeric min_lat, max_lat, min_lon, max_lon.")
            min_lat = max_lat = min_lon = max_lon = 0.0

        if min_lat and max_lat and min_lon and max_lon:
            if not (INDIA_LAT_MIN <= min_lat <= max_lat <= INDIA_LAT_MAX):
                errors.append(f"Latitude bounds [{min_lat}, {max_lat}] out of valid territorial limits [{INDIA_LAT_MIN}, {INDIA_LAT_MAX}].")
            if not (INDIA_LON_MIN <= min_lon <= max_lon <= INDIA_LON_MAX):
                errors.append(f"Longitude bounds [{min_lon}, {max_lon}] out of valid territorial limits [{INDIA_LON_MIN}, {INDIA_LON_MAX}].")
            if min_lat >= max_lat:
                errors.append(f"min_lat ({min_lat}) must be strictly less than max_lat ({max_lat}).")
            if min_lon >= max_lon:
                errors.append(f"min_lon ({min_lon}) must be strictly less than max_lon ({max_lon}).")

        # 3. Model Support Separation Rule
        model_support_status = str(payload.get("model_support_status") or "UNSUPPORTED").upper()
        allowed_model_statuses = {"MODEL_SUPPORTED", "VALIDATION_PENDING", "UNSUPPORTED", "NO_MODEL"}
        if model_support_status not in allowed_model_statuses:
            errors.append(f"Invalid 'model_support_status': '{model_support_status}'. Allowed: {sorted(list(allowed_model_statuses))}")

        is_synthetic = bool(payload.get("is_synthetic", False))
        if is_synthetic and model_support_status == "MODEL_SUPPORTED":
            errors.append("Model Support Violation: Synthetic test fixtures cannot claim 'MODEL_SUPPORTED' status. Status must be 'VALIDATION_PENDING' or 'UNSUPPORTED'.")

        supported_model_version = payload.get("supported_model_version")
        if model_support_status == "MODEL_SUPPORTED" and not supported_model_version:
            errors.append("Model Support Violation: 'MODEL_SUPPORTED' requires a specified 'supported_model_version' that has passed Phase 10 promotion gates.")

        # Delhi model cannot be assigned to another region without transfer evaluation
        if region_id != "delhi" and supported_model_version == "cashout-location-xgb-v7-compat":
            errors.append("Cross-Region Leakage: The Delhi-trained model 'cashout-location-xgb-v7-compat' cannot be claimed as supported for a non-Delhi region without verified transfer evaluation.")

        # 4. Cluster Validation & Deduplication
        clusters = payload.get("clusters") or []
        if not isinstance(clusters, list) or len(clusters) == 0:
            errors.append("Missing or empty 'clusters' list in catalog payload.")
        else:
            seen_cluster_names = set()
            seen_cluster_ids = set()
            for idx, c in enumerate(clusters):
                c_id = c.get("id")
                if c_id is not None:
                    if c_id in seen_cluster_ids:
                        errors.append(f"Duplicate cluster ID: Cluster ID '{c_id}' appears multiple times in catalog.")
                    else:
                        seen_cluster_ids.add(c_id)

                c_name = str(c.get("cluster_name") or c.get("name") or "").strip()
                if not c_name:
                    errors.append(f"Cluster #{idx}: Missing cluster 'name'.")
                elif c_name in seen_cluster_names:
                    errors.append(f"Duplicate cluster identity: '{c_name}' appears multiple times in catalog.")
                else:
                    seen_cluster_names.add(c_name)

                try:
                    c_lat = float(c.get("latitude") if c.get("latitude") is not None else c.get("lat"))
                    c_lon = float(c.get("longitude") if c.get("longitude") is not None else c.get("lon"))
                except (TypeError, ValueError):
                    errors.append(f"Cluster '{c_name}': Non-numeric or missing coordinates.")
                    continue

                if not (math.isfinite(c_lat) and math.isfinite(c_lon)):
                    errors.append(f"Cluster '{c_name}': Coordinates must be finite numbers.")
                    continue

                # Bounds check
                if min_lat and max_lat and min_lon and max_lon:
                    if not (min_lat <= c_lat <= max_lat and min_lon <= c_lon <= max_lon):
                        errors.append(
                            f"Cluster '{c_name}' coordinates ({c_lat}, {c_lon}) fall outside declared regional bounding box "
                            f"[{min_lat}, {max_lat}] x [{min_lon}, {max_lon}]."
                        )

                # Cross-region boundary checks (prevent Delhi coordinates inside Mumbai catalog and vice versa)
                if region_id != "delhi" and (28.38 <= c_lat <= 28.92 and 76.80 <= c_lon <= 77.45):
                    errors.append(f"Cross-Region Leakage: Cluster '{c_name}' coordinates fall inside Delhi Pilot bounds but catalog is for region '{region_id}'.")
                if region_id == "delhi" and not (28.38 <= c_lat <= 28.92 and 76.80 <= c_lon <= 77.45):
                    errors.append(f"Cluster '{c_name}' coordinates ({c_lat}, {c_lon}) fall outside Delhi Pilot boundary.")

        # 5. ATM Validation & Deduplication
        atms = payload.get("atms") or []
        if isinstance(atms, list):
            seen_atm_codes = set()
            for idx, a in enumerate(atms):
                atm_code = str(a.get("atm_code") or "").strip()
                if not atm_code:
                    errors.append(f"ATM #{idx}: Missing 'atm_code'.")
                elif atm_code in seen_atm_codes:
                    errors.append(f"Duplicate ATM code: ATM code '{atm_code}' appears multiple times in catalog.")
                else:
                    seen_atm_codes.add(atm_code)

                try:
                    a_lat = float(a.get("latitude") if a.get("latitude") is not None else a.get("lat"))
                    a_lon = float(a.get("longitude") if a.get("longitude") is not None else a.get("lon"))
                except (TypeError, ValueError):
                    errors.append(f"ATM '{atm_code}': Non-numeric or missing coordinates.")
                    continue

                if not (math.isfinite(a_lat) and math.isfinite(a_lon)):
                    errors.append(f"ATM '{atm_code}': Coordinates must be finite numbers.")
                    continue

                if min_lat and max_lat and min_lon and max_lon:
                    if not (min_lat <= a_lat <= max_lat and min_lon <= a_lon <= max_lon):
                        errors.append(f"ATM '{atm_code}' coordinates ({a_lat}, {a_lon}) fall outside regional bounding box.")

        # 6. Organization Mapping Check (if DB provided)
        org_mappings = payload.get("organization_ids") or []
        if db is not None and org_mappings:
            for org_id in org_mappings:
                org = db.query(Organization).filter(Organization.id == org_id).first()
                if not org:
                    errors.append(f"Organization Mapping Error: Organization id={org_id} does not exist.")
                elif org.state and payload.get("state") and org.state.lower() != str(payload.get("state")).lower():
                    warnings.append(
                        f"Organization Mapping Warning: Organization '{org.name}' state '{org.state}' "
                        f"cannot be mapped to catalog region '{region_id}' (state='{payload.get('state')}')."
                    )

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "is_valid": is_valid,
            "region_id": region_id,
            "catalog_version": catalog_version,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "clusters_count": len(clusters),
                "atms_count": len(atms),
                "model_support_status": model_support_status,
                "is_synthetic": is_synthetic,
            }
        }

    @classmethod
    def validate_catalog_payload(
        cls,
        region_meta: Dict[str, Any],
        clusters: List[Dict[str, Any]],
        atms: List[Dict[str, Any]],
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Convenience helper for validating modular payload components."""
        payload = dict(region_meta)
        payload["clusters"] = clusters
        payload["atms"] = atms
        res = cls.validate_catalog(payload, db=db)
        res["valid"] = res["is_valid"]
        return res


def get_registered_regions(db: Session, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Returns list of registered geography regions with operational metadata."""
    query = db.query(Region)
    if not include_inactive:
        query = query.filter(Region.is_active == True)
    regions = query.order_by(Region.id.asc()).all()
    res = []
    for r in regions:
        cluster_cnt = db.query(func.count(LocationCluster.id)).filter(LocationCluster.region_id == r.id).scalar() or 0
        atm_cnt = db.query(func.count(ATMLocation.id)).filter(ATMLocation.region_id == r.id).scalar() or 0
        res.append({
            "id": r.id,
            "name": r.name,
            "state": r.state,
            "catalog_version": r.catalog_version,
            "source": r.source,
            "license": r.license,
            "verification_time": r.verification_time.isoformat() if r.verification_time else None,
            "center": {"lat": r.center_lat, "lon": r.center_lon},
            "bounds": {
                "min_lat": r.bounds_min_lat,
                "max_lat": r.bounds_max_lat,
                "min_lon": r.bounds_min_lon,
                "max_lon": r.bounds_max_lon,
            },
            "cluster_radius_km": r.cluster_radius_km,
            "districts": r.districts or [],
            "total_clusters": cluster_cnt,
            "total_atms": atm_cnt,
            "data_completeness_status": r.data_completeness_status,
            "model_support_status": r.model_support_status,
            "supported_model_version": r.supported_model_version,
            "is_synthetic": r.is_synthetic,
            "is_active": r.is_active,
        })
    return res


def get_region_by_id(db: Session, region_id: str) -> Optional[Region]:
    """Retrieves region by identifier."""
    return db.query(Region).filter(Region.id == region_id.strip().lower()).first()


def resolve_region_for_complaint(
    db: Session,
    state: Optional[str] = None,
    district: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    explicit_region_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Region]]:
    """
    Deterministically resolves region_id for a complaint.
    Strict Rules:
      - If explicit_region_id is provided and valid, returns that region.
      - If state/district matches a registered region, returns that region.
      - If lat/lon provided and strictly within region bounds, returns that region.
      - NO silent Delhi fallback for non-Delhi locations!
    """
    if explicit_region_id:
        r = get_region_by_id(db, explicit_region_id)
        if r:
            return r.id, r

    s = (state or "").strip().lower()
    d = (district or "").strip().upper()

    # Match Delhi
    if s in ("delhi", "nct of delhi", "new delhi"):
        r = get_region_by_id(db, "delhi")
        return "delhi", r

    # Match Maharashtra / Mumbai
    if s == "maharashtra" or d in ("MUMBAI", "MUMBAI_SUBURBAN", "THANE", "NAVI_MUMBAI"):
        r = get_region_by_id(db, "mumbai_mmr")
        return "mumbai_mmr", r

    # Coordinate bounding box matching
    if lat is not None and lon is not None and math.isfinite(lat) and math.isfinite(lon):
        regions = db.query(Region).filter(Region.is_active == True).all()
        for r in regions:
            if r.bounds_min_lat <= lat <= r.bounds_max_lat and r.bounds_min_lon <= lon <= r.bounds_max_lon:
                return r.id, r

    return None, None


def ensure_default_regions_and_catalogs(db: Session) -> None:
    """Ensures Delhi and synthetic Mumbai MMR fixtures exist in the database."""
    # 1. Delhi Region
    delhi = db.query(Region).filter(Region.id == "delhi").first()
    if not delhi:
        delhi = Region(
            id="delhi",
            name="National Capital Territory of Delhi",
            state="Delhi",
            catalog_version="delhi_pilot_v1.0",
            source="Delhi Police Open Data / Survey of India / SIH-2024 Baseline",
            license="Government Open Data License (India) / Research Use",
            verification_time=datetime.datetime(2026, 9, 17, 0, 0, 0, tzinfo=datetime.timezone.utc),
            center_lat=28.6360,
            center_lon=77.1989,
            bounds_min_lat=28.38,
            bounds_max_lat=28.92,
            bounds_min_lon=76.80,
            bounds_max_lon=77.45,
            cluster_radius_km=2.5,
            districts=DELHI_DISTRICTS,
            data_completeness_status="COMPLETE",
            model_support_status="MODEL_SUPPORTED",
            supported_model_version="cashout-location-xgb-v7-compat",
            is_synthetic=False,
            is_active=True,
        )
        db.add(delhi)
        db.flush()

    # 2. Mumbai MMR Synthetic Second-Region Test Fixture
    mumbai = db.query(Region).filter(Region.id == "mumbai_mmr").first()
    if not mumbai:
        mumbai = Region(
            id="mumbai_mmr",
            name="Mumbai Metropolitan Region (Synthetic Test Fixture)",
            state="Maharashtra",
            catalog_version="mumbai_synthetic_test_v1.0",
            source="Synthetic Test Fixture for Functional Workflow Verification",
            license="Internal Non-Operational Research Test License — NOT FOR OPERATIONAL USE",
            verification_time=None,
            center_lat=19.0760,
            center_lon=72.8777,
            bounds_min_lat=18.85,
            bounds_max_lat=19.35,
            bounds_min_lon=72.75,
            bounds_max_lon=73.15,
            cluster_radius_km=3.0,
            districts=MUMBAI_DISTRICTS,
            data_completeness_status="SYNTHETIC_FIXTURE_ONLY",
            model_support_status="VALIDATION_PENDING",
            supported_model_version=None,
            is_synthetic=True,
            is_active=True,
        )
        db.add(mumbai)
        db.flush()

    # 3. Seed Synthetic Mumbai Clusters & ATMs if absent
    existing_mumbai_clusters = db.query(LocationCluster).filter(LocationCluster.region_id == "mumbai_mmr").count()
    if existing_mumbai_clusters == 0:
        cluster_map: Dict[str, LocationCluster] = {}
        for sc in SYNTHETIC_MUMBAI_CLUSTERS:
            cl = LocationCluster(
                cluster_name=sc["name"],
                city=sc["city"],
                district=sc["district"],
                state=sc["state"],
                region_id="mumbai_mmr",
                center_lat=sc["lat"],
                center_lon=sc["lon"],
                radius_km=sc["radius"],
                historical_fraud_count=sc["fraud_count"],
                atm_count=sc["atm_count"],
                risk_score=sc["risk"],
            )
            db.add(cl)
            db.flush()
            cluster_map[sc["name"]] = cl

        for sa in SYNTHETIC_MUMBAI_ATMS:
            c_obj = cluster_map.get(sa["cluster_name"])
            atm = ATMLocation(
                atm_code=sa["atm_code"],
                bank_name=sa["bank_name"],
                address=sa["address"],
                city=sa["city"],
                district=sa["district"],
                state=sa["state"],
                region_id="mumbai_mmr",
                latitude=sa["latitude"],
                longitude=sa["longitude"],
                cash_available=True,
                risk_rating="MEDIUM",
                cluster_id=c_obj.id if c_obj else None,
            )
            db.add(atm)

    # 4. Explicitly ensure Delhi records have region_id='delhi' and non-Delhi records do NOT
    db.query(LocationCluster).filter(
        LocationCluster.state == "Delhi",
        LocationCluster.center_lat >= 28.38, LocationCluster.center_lat <= 28.92,
        LocationCluster.center_lon >= 76.80, LocationCluster.center_lon <= 77.45
    ).update({"region_id": "delhi"}, synchronize_session=False)

    db.query(ATMLocation).filter(
        ATMLocation.state == "Delhi",
        ATMLocation.latitude >= 28.38, ATMLocation.latitude <= 28.92,
        ATMLocation.longitude >= 76.80, ATMLocation.longitude <= 77.45
    ).update({"region_id": "delhi"}, synchronize_session=False)

    db.query(LocationCluster).filter(LocationCluster.state != "Delhi", LocationCluster.region_id == "delhi").update({"region_id": None}, synchronize_session=False)
    db.query(ATMLocation).filter(ATMLocation.state != "Delhi", ATMLocation.region_id == "delhi").update({"region_id": None}, synchronize_session=False)
    db.query(Complaint).filter(Complaint.state != "Delhi", Complaint.region_id == "delhi").update({"region_id": None}, synchronize_session=False)
    db.query(Organization).filter(Organization.state != "Delhi", Organization.region_id == "delhi").update({"region_id": None}, synchronize_session=False)

    db.commit()
