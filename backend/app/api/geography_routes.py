"""CyberShield AI — Geography Catalog and Region Management Routes.
Phase 12: Configurable Geography & Second-Region Readiness Gate.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import Region, GeographyCatalog, LocationCluster, ATMLocation, User
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import require_roles, RoleEnum, is_national_scope
from backend.app.schemas.schemas import (
    RegionSummaryItem,
    RegionDetailResponse,
    GeographyCatalogResponseItem,
    CatalogValidationRequest,
    CatalogValidationResponse,
    CatalogImportRequest,
    CatalogImportResponse,
)
from backend.app.services.geography_catalog_service import (
    get_registered_regions,
    get_region_by_id,
    ensure_default_regions_and_catalogs,
    GeographyCatalogValidator,
)

router = APIRouter(prefix="/geography", tags=["Geography & Regions"])


@router.get("/regions", response_model=List[RegionSummaryItem])
def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all registered geographic regions and their operational/model support status.
    Accessible to all authenticated users.
    """
    ensure_default_regions_and_catalogs(db)
    return get_registered_regions(db)


@router.get("/regions/{region_id}", response_model=RegionDetailResponse)
def get_region_detail(
    region_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed operational metadata, bounds, and limitations for a specific region.
    """
    ensure_default_regions_and_catalogs(db)
    r = get_region_by_id(db, region_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{region_id}' is not registered in the Geography Catalog."
        )

    cluster_cnt = db.query(LocationCluster).filter(LocationCluster.region_id == r.id).count()
    atm_cnt = db.query(ATMLocation).filter(ATMLocation.region_id == r.id).count()
    clusters_sample = db.query(LocationCluster).filter(LocationCluster.region_id == r.id).limit(10).all()

    limitations = []
    if r.model_support_status == "VALIDATION_PENDING":
        limitations.append(
            f"Region '{r.name}' ({r.id}) has catalog coordinates registered, but predictive model validation is PENDING. "
            "Inferences are disabled for this region; no silent Delhi fallback predictions will be produced."
        )
    elif r.model_support_status == "UNSUPPORTED":
        limitations.append(
            f"No trained predictive models exist for region '{r.name}'. Predictions are strictly unavailable."
        )
    elif r.is_synthetic:
        limitations.append(
            "This region is a synthetic test fixture reserved for workflow verification; not for operational field deployment."
        )

    summary_item = RegionSummaryItem(
        id=r.id,
        name=r.name,
        state=r.state,
        catalog_version=r.catalog_version,
        source=r.source,
        license=r.license,
        verification_time=r.verification_time.isoformat() if r.verification_time else None,
        center={"lat": r.center_lat, "lon": r.center_lon},
        bounds={
            "min_lat": r.bounds_min_lat,
            "max_lat": r.bounds_max_lat,
            "min_lon": r.bounds_min_lon,
            "max_lon": r.bounds_max_lon,
        },
        cluster_radius_km=r.cluster_radius_km,
        districts=r.districts or [],
        total_clusters=cluster_cnt,
        total_atms=atm_cnt,
        data_completeness_status=r.data_completeness_status,
        model_support_status=r.model_support_status,
        supported_model_version=r.supported_model_version,
        is_synthetic=r.is_synthetic,
        is_active=r.is_active,
    )

    clusters_data = [
        {
            "id": c.id,
            "cluster_name": c.cluster_name,
            "district": c.district,
            "city": c.city,
            "center_lat": c.center_lat,
            "center_lon": c.center_lon,
            "radius_km": c.radius_km,
            "risk_score": c.risk_score,
            "atm_count": c.atm_count,
        }
        for c in clusters_sample
    ]

    res_dict = summary_item.model_dump()
    res_dict["region"] = summary_item
    res_dict["clusters_sample"] = clusters_data
    res_dict["operational_limitations"] = limitations
    return res_dict


@router.get("/regions/{region_id}/clusters")
def get_region_clusters(
    region_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all clusters in a specific region.
    Preserves role-based jurisdiction boundaries:
      - Non-national LEA users cannot read clusters outside their jurisdiction.
    """
    ensure_default_regions_and_catalogs(db)
    r = get_region_by_id(db, region_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{region_id}' not found."
        )

    # Server-side jurisdiction check: region selection must never expand access
    if not is_national_scope(current_user):
        org = current_user.organization
        if org and org.state and r.state and org.state.strip().lower() != r.state.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: User organization '{org.name}' ({org.state}) cannot access clusters in region '{r.name}' ({r.state})."
            )

    clusters = db.query(LocationCluster).filter(LocationCluster.region_id == r.id).order_by(LocationCluster.id.asc()).all()
    return [
        {
            "id": c.id,
            "cluster_name": c.cluster_name,
            "city": c.city,
            "district": c.district,
            "state": c.state,
            "region_id": c.region_id,
            "center_lat": c.center_lat,
            "center_lon": c.center_lon,
            "latitude": c.center_lat,
            "longitude": c.center_lon,
            "radius_km": c.radius_km,
            "risk_score": c.risk_score,
            "atm_count": c.atm_count,
            "historical_fraud_count": c.historical_fraud_count,
        }
        for c in clusters
    ]


@router.get("/catalogs", response_model=List[GeographyCatalogResponseItem])
def list_catalogs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all versioned geography catalogs and their audit provenance.
    """
    ensure_default_regions_and_catalogs(db)
    catalogs = db.query(GeographyCatalog).order_by(GeographyCatalog.id.asc()).all()
    res = []
    for cat in catalogs:
        res.append({
            "id": cat.id,
            "catalog_id": cat.catalog_id,
            "region_id": cat.region_id,
            "catalog_version": cat.catalog_version,
            "source": cat.source,
            "license": cat.license,
            "provenance_notes": cat.provenance_notes,
            "verification_time": cat.verification_time.isoformat() if cat.verification_time else None,
            "status": cat.status,
            "data_completeness_status": cat.data_completeness_status,
            "model_support_status": cat.model_support_status,
            "supported_model_version": cat.supported_model_version,
            "total_clusters": cat.total_clusters,
            "total_atms": cat.total_atms,
            "cluster_radius_km": cat.cluster_radius_km,
            "imported_at": cat.imported_at.isoformat() if cat.imported_at else None,
        })
    return res


@router.post("/validate", response_model=CatalogValidationResponse)
def validate_catalog(
    req: CatalogValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dry-run validation of a geography catalog import payload.
    Checks coordinate bounds, duplicate identities, licensing, and model support rules.
    Does not modify database state.
    """
    result = GeographyCatalogValidator.validate_catalog(req.catalog, db=db)
    return {
        "is_valid": result["is_valid"],
        "region_id": result["region_id"],
        "catalog_version": result["catalog_version"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "summary": result["summary"],
    }


@router.post("/import", response_model=CatalogImportResponse)
def import_catalog(
    req: CatalogImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN)),
):
    """
    Import a validated geography catalog into the system.
    Restricted to I4C_ADMIN.
    """
    val = GeographyCatalogValidator.validate_catalog(req.catalog, db=db)
    if not val["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Geography catalog validation failed.",
                "errors": val["errors"]
            }
        )

    cat_data = req.catalog
    region_id = cat_data["region_id"].strip().lower()
    bounds = cat_data["bounds"]

    # Upsert Region
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        region = Region(id=region_id)
        db.add(region)

    region.name = cat_data["region_name"]
    region.state = cat_data.get("state") or "Other"
    region.catalog_version = cat_data["catalog_version"]
    region.source = cat_data["source"]
    region.license = cat_data["license"]
    region.center_lat = float(cat_data.get("center_lat", (bounds["min_lat"] + bounds["max_lat"]) / 2))
    region.center_lon = float(cat_data.get("center_lon", (bounds["min_lon"] + bounds["max_lon"]) / 2))
    region.bounds_min_lat = float(bounds["min_lat"])
    region.bounds_max_lat = float(bounds["max_lat"])
    region.bounds_min_lon = float(bounds["min_lon"])
    region.bounds_max_lon = float(bounds["max_lon"])
    region.cluster_radius_km = float(cat_data.get("cluster_radius_km", 2.5))
    region.districts = cat_data.get("districts") or []
    region.data_completeness_status = cat_data.get("data_completeness_status", "COMPLETE")
    region.model_support_status = cat_data.get("model_support_status", "UNSUPPORTED")
    region.supported_model_version = cat_data.get("supported_model_version")
    region.is_synthetic = bool(cat_data.get("is_synthetic", False))
    region.is_active = True
    db.flush()

    # Import clusters
    clusters_data = cat_data.get("clusters") or []
    total_clusters = 0
    cluster_obj_map = {}
    for c in clusters_data:
        existing = db.query(LocationCluster).filter(
            LocationCluster.region_id == region_id,
            LocationCluster.cluster_name == c["name"]
        ).first()
        if not existing:
            existing = LocationCluster(
                cluster_name=c["name"],
                city=c.get("city") or region.name,
                district=c.get("district") or "GENERAL",
                state=region.state,
                region_id=region_id,
                center_lat=float(c["lat"]),
                center_lon=float(c["lon"]),
                radius_km=float(c.get("radius", region.cluster_radius_km)),
                historical_fraud_count=int(c.get("fraud_count", 0)),
                atm_count=int(c.get("atm_count", 0)),
                risk_score=float(c.get("risk", 0.5)),
            )
            db.add(existing)
            db.flush()
        cluster_obj_map[c["name"]] = existing
        total_clusters += 1

    # Import ATMs
    atms_data = cat_data.get("atms") or []
    total_atms = 0
    for a in atms_data:
        existing_atm = db.query(ATMLocation).filter(ATMLocation.atm_code == a["atm_code"]).first()
        c_obj = cluster_obj_map.get(a.get("cluster_name"))
        if not existing_atm:
            existing_atm = ATMLocation(
                atm_code=a["atm_code"],
                bank_name=a.get("bank_name", "General Bank"),
                address=a.get("address", "ATM Terminal"),
                city=a.get("city", region.name),
                district=a.get("district", "GENERAL"),
                state=region.state,
                region_id=region_id,
                latitude=float(a["latitude"]),
                longitude=float(a["longitude"]),
                cash_available=True,
                risk_rating="MEDIUM",
                cluster_id=c_obj.id if c_obj else None,
            )
            db.add(existing_atm)
        total_atms += 1

    # Create Catalog Entry
    catalog_id = f"CAT-{region_id.upper()}-{cat_data['catalog_version'].upper()}"
    cat_entry = db.query(GeographyCatalog).filter(GeographyCatalog.catalog_id == catalog_id).first()
    if not cat_entry:
        cat_entry = GeographyCatalog(catalog_id=catalog_id, region_id=region_id)
        db.add(cat_entry)

    cat_entry.catalog_version = cat_data["catalog_version"]
    cat_entry.source = cat_data["source"]
    cat_entry.license = cat_data["license"]
    cat_entry.provenance_notes = cat_data.get("provenance_notes")
    cat_entry.status = "ACTIVE"
    cat_entry.data_completeness_status = region.data_completeness_status
    cat_entry.model_support_status = region.model_support_status
    cat_entry.supported_model_version = region.supported_model_version
    cat_entry.total_clusters = total_clusters
    cat_entry.total_atms = total_atms
    cat_entry.cluster_radius_km = region.cluster_radius_km
    cat_entry.imported_by_user_id = current_user.id

    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Successfully imported geography catalog for region '{region.name}' ({region.id}).",
        "catalog_id": catalog_id,
        "region_id": region_id,
        "total_clusters_imported": total_clusters,
        "total_atms_imported": total_atms,
        "model_support_status": region.model_support_status,
    }
