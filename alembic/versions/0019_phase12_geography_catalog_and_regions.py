"""Add Phase 12 geography catalog, regions, and multi-region routing support.

Revision ID: 0019_phase12_geography_catalog_and_regions
Revises: 0018_phase9_outcome_observations

Phase 12: Configurable Geography & Second-Region Readiness Gate.
Introduces:
  1. `regions` table: Explicit region registry with bounding box, provenance,
     model support status, and completeness status.
  2. `geography_catalogs` table: Versioned geography catalog tracking source,
     license, verification time, and candidate identities.
  3. `region_id` column added to `location_clusters`, `atm_locations`,
     `complaints`, and `organizations`.
  4. Seed records for Delhi Pilot (MODEL_SUPPORTED) and synthetic second region
     Mumbai MMR (VALIDATION_PENDING, labelled synthetic test fixture).
  5. Backfills existing operational Delhi rows to explicit region_id='delhi'.
"""
import json
import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0019_phase12_geography_catalog_and_regions"
down_revision = "0018_phase9_outcome_observations"
branch_labels = None
depends_on = None


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

MUMBAI_DISTRICTS = [
    "MUMBAI",
    "MUMBAI_SUBURBAN",
    "THANE",
    "NAVI_MUMBAI"
]


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    def get_column_names(table_name):
        try:
            return {c["name"] for c in insp.get_columns(table_name)}
        except Exception:
            return set()

    def get_existing_indexes(table_name):
        try:
            return {ix["name"] for ix in insp.get_indexes(table_name)}
        except Exception:
            return set()

    # 1. Create `regions` table if not exists
    if not insp.has_table("regions"):
        op.create_table(
            "regions",
            sa.Column("id", sa.String(50), primary_key=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("state", sa.String(100), nullable=False),
            sa.Column("catalog_version", sa.String(50), nullable=False),
            sa.Column("source", sa.String(255), nullable=False),
            sa.Column("license", sa.String(255), nullable=False),
            sa.Column("verification_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("center_lat", sa.Float(), nullable=False),
            sa.Column("center_lon", sa.Float(), nullable=False),
            sa.Column("bounds_min_lat", sa.Float(), nullable=False),
            sa.Column("bounds_max_lat", sa.Float(), nullable=False),
            sa.Column("bounds_min_lon", sa.Float(), nullable=False),
            sa.Column("bounds_max_lon", sa.Float(), nullable=False),
            sa.Column("cluster_radius_km", sa.Float(), server_default="2.5", nullable=False),
            sa.Column("districts", sa.JSON(), nullable=True),
            sa.Column("data_completeness_status", sa.String(50), server_default="COMPLETE", nullable=False),
            sa.Column("model_support_status", sa.String(50), server_default="UNSUPPORTED", nullable=False),
            sa.Column("supported_model_version", sa.String(100), nullable=True),
            sa.Column("is_synthetic", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_regions_id", "regions", ["id"])
        op.create_index("ix_regions_state", "regions", ["state"])
        op.create_index("ix_regions_model_support_status", "regions", ["model_support_status"])

    # 2. Create `geography_catalogs` table if not exists
    if not insp.has_table("geography_catalogs"):
        op.create_table(
            "geography_catalogs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("catalog_id", sa.String(100), unique=True, nullable=False),
            sa.Column("region_id", sa.String(50), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("catalog_version", sa.String(50), nullable=False),
            sa.Column("source", sa.String(255), nullable=False),
            sa.Column("license", sa.String(255), nullable=False),
            sa.Column("provenance_notes", sa.Text(), nullable=True),
            sa.Column("verification_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(50), server_default="ACTIVE", nullable=False),
            sa.Column("data_completeness_status", sa.String(50), server_default="COMPLETE", nullable=False),
            sa.Column("model_support_status", sa.String(50), server_default="UNSUPPORTED", nullable=False),
            sa.Column("supported_model_version", sa.String(100), nullable=True),
            sa.Column("total_clusters", sa.Integer(), server_default="0", nullable=False),
            sa.Column("total_atms", sa.Integer(), server_default="0", nullable=False),
            sa.Column("cluster_radius_km", sa.Float(), server_default="2.5", nullable=False),
            sa.Column("catalog_payload", sa.JSON(), nullable=True),
            sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("imported_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_geography_catalogs_id", "geography_catalogs", ["id"])
        op.create_index("ix_geography_catalogs_catalog_id", "geography_catalogs", ["catalog_id"])
        op.create_index("ix_geography_catalogs_region_id", "geography_catalogs", ["region_id"])
        op.create_index("ix_geography_catalogs_status", "geography_catalogs", ["status"])

    # 3. Add `region_id` to existing tables
    lc_cols = get_column_names("location_clusters")
    lc_ixs = get_existing_indexes("location_clusters")
    if "region_id" not in lc_cols:
        op.add_column("location_clusters", sa.Column("region_id", sa.String(50), nullable=True, server_default="delhi"))
    if "ix_location_clusters_region_id" not in lc_ixs:
        op.create_index("ix_location_clusters_region_id", "location_clusters", ["region_id"])

    atm_cols = get_column_names("atm_locations")
    atm_ixs = get_existing_indexes("atm_locations")
    if "region_id" not in atm_cols:
        op.add_column("atm_locations", sa.Column("region_id", sa.String(50), nullable=True, server_default="delhi"))
    if "ix_atm_locations_region_id" not in atm_ixs:
        op.create_index("ix_atm_locations_region_id", "atm_locations", ["region_id"])

    complaint_cols = get_column_names("complaints")
    complaint_ixs = get_existing_indexes("complaints")
    if "region_id" not in complaint_cols:
        op.add_column("complaints", sa.Column("region_id", sa.String(50), nullable=True, server_default="delhi"))
    if "ix_complaints_region_id" not in complaint_ixs:
        op.create_index("ix_complaints_region_id", "complaints", ["region_id"])

    org_cols = get_column_names("organizations")
    org_ixs = get_existing_indexes("organizations")
    if "region_id" not in org_cols:
        op.add_column("organizations", sa.Column("region_id", sa.String(50), nullable=True, server_default="delhi"))
    if "ix_organizations_region_id" not in org_ixs:
        op.create_index("ix_organizations_region_id", "organizations", ["region_id"])

    # 4. Seed baseline regions into `regions`
    existing_regions = set()
    try:
        res = bind.execute(sa.text("SELECT id FROM regions")).fetchall()
        existing_regions = {r[0] for r in res}
    except Exception:
        pass

    regions_table = sa.table(
        "regions",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("state", sa.String),
        sa.column("catalog_version", sa.String),
        sa.column("source", sa.String),
        sa.column("license", sa.String),
        sa.column("verification_time", sa.DateTime(timezone=True)),
        sa.column("center_lat", sa.Float),
        sa.column("center_lon", sa.Float),
        sa.column("bounds_min_lat", sa.Float),
        sa.column("bounds_max_lat", sa.Float),
        sa.column("bounds_min_lon", sa.Float),
        sa.column("bounds_max_lon", sa.Float),
        sa.column("cluster_radius_km", sa.Float),
        sa.column("districts", sa.JSON),
        sa.column("data_completeness_status", sa.String),
        sa.column("model_support_status", sa.String),
        sa.column("supported_model_version", sa.String),
        sa.column("is_synthetic", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )

    delhi_ver_time = datetime.datetime(2026, 9, 17, 0, 0, 0, tzinfo=datetime.timezone.utc)

    regions_to_insert = []
    if "delhi" not in existing_regions:
        regions_to_insert.append({
            "id": "delhi",
            "name": "National Capital Territory of Delhi",
            "state": "Delhi",
            "catalog_version": "delhi_pilot_v1.0",
            "source": "Delhi Police Open Data / Survey of India / SIH-2024 Baseline",
            "license": "Government Open Data License (India) / Research Use",
            "verification_time": delhi_ver_time,
            "center_lat": 28.6360,
            "center_lon": 77.1989,
            "bounds_min_lat": 28.38,
            "bounds_max_lat": 28.92,
            "bounds_min_lon": 76.80,
            "bounds_max_lon": 77.45,
            "cluster_radius_km": 2.5,
            "districts": DELHI_DISTRICTS,
            "data_completeness_status": "COMPLETE",
            "model_support_status": "MODEL_SUPPORTED",
            "supported_model_version": "cashout-location-xgb-v7-compat",
            "is_synthetic": False,
            "is_active": True,
        })
    if "mumbai_mmr" not in existing_regions:
        regions_to_insert.append({
            "id": "mumbai_mmr",
            "name": "Mumbai Metropolitan Region (Synthetic Test Fixture)",
            "state": "Maharashtra",
            "catalog_version": "mumbai_synthetic_test_v1.0",
            "source": "Synthetic Test Fixture for Functional Workflow Verification",
            "license": "Internal Non-Operational Research Test License — NOT FOR OPERATIONAL USE",
            "verification_time": None,
            "center_lat": 19.0760,
            "center_lon": 72.8777,
            "bounds_min_lat": 18.85,
            "bounds_max_lat": 19.35,
            "bounds_min_lon": 72.75,
            "bounds_max_lon": 73.15,
            "cluster_radius_km": 3.0,
            "districts": MUMBAI_DISTRICTS,
            "data_completeness_status": "SYNTHETIC_FIXTURE_ONLY",
            "model_support_status": "VALIDATION_PENDING",
            "supported_model_version": None,
            "is_synthetic": True,
            "is_active": True,
        })

    if regions_to_insert:
        op.bulk_insert(regions_table, regions_to_insert)

    # 5. Seed initial geography catalog entries
    existing_catalogs = set()
    try:
        res = bind.execute(sa.text("SELECT catalog_id FROM geography_catalogs")).fetchall()
        existing_catalogs = {r[0] for r in res}
    except Exception:
        pass

    catalogs_table = sa.table(
        "geography_catalogs",
        sa.column("id", sa.Integer),
        sa.column("catalog_id", sa.String),
        sa.column("region_id", sa.String),
        sa.column("catalog_version", sa.String),
        sa.column("source", sa.String),
        sa.column("license", sa.String),
        sa.column("provenance_notes", sa.Text),
        sa.column("verification_time", sa.DateTime(timezone=True)),
        sa.column("status", sa.String),
        sa.column("data_completeness_status", sa.String),
        sa.column("model_support_status", sa.String),
        sa.column("supported_model_version", sa.String),
        sa.column("total_clusters", sa.Integer),
        sa.column("total_atms", sa.Integer),
        sa.column("cluster_radius_km", sa.Float),
        sa.column("catalog_payload", sa.JSON),
    )

    catalogs_to_insert = []
    if "CAT-DL-PILOT-V1" not in existing_catalogs:
        catalogs_to_insert.append({
            "catalog_id": "CAT-DL-PILOT-V1",
            "region_id": "delhi",
            "catalog_version": "delhi_pilot_v1.0",
            "source": "Delhi Police Open Data / Survey of India / SIH-2024 Baseline",
            "license": "Government Open Data License (India) / Research Use",
            "provenance_notes": "Official 60 operational clusters across 9 NCT zones calibrated with XGBoost V7-compat.",
            "verification_time": delhi_ver_time,
            "status": "ACTIVE",
            "data_completeness_status": "COMPLETE",
            "model_support_status": "MODEL_SUPPORTED",
            "supported_model_version": "cashout-location-xgb-v7-compat",
            "total_clusters": 60,
            "total_atms": 240,
            "cluster_radius_km": 2.5,
            "catalog_payload": None,
        })
    if "CAT-MUM-SYN-V1" not in existing_catalogs:
        catalogs_to_insert.append({
            "catalog_id": "CAT-MUM-SYN-V1",
            "region_id": "mumbai_mmr",
            "catalog_version": "mumbai_synthetic_test_v1.0",
            "source": "Synthetic Test Fixture for Functional Workflow Verification",
            "license": "Internal Non-Operational Research Test License — NOT FOR OPERATIONAL USE",
            "provenance_notes": "Labelled synthetic fixture for functional workflow verification. Predictive model validation PENDING.",
            "verification_time": None,
            "status": "ACTIVE",
            "data_completeness_status": "SYNTHETIC_FIXTURE_ONLY",
            "model_support_status": "VALIDATION_PENDING",
            "supported_model_version": None,
            "total_clusters": 6,
            "total_atms": 12,
            "cluster_radius_km": 3.0,
            "catalog_payload": None,
        })

    if catalogs_to_insert:
        op.bulk_insert(catalogs_table, catalogs_to_insert)

    # 6. Backfill existing Delhi data
    bind.execute(sa.text("UPDATE location_clusters SET region_id = 'delhi' WHERE region_id IS NULL OR LOWER(state) = 'delhi'"))
    bind.execute(sa.text("UPDATE atm_locations SET region_id = 'delhi' WHERE region_id IS NULL OR LOWER(state) = 'delhi'"))
    bind.execute(sa.text("UPDATE complaints SET region_id = 'delhi' WHERE region_id IS NULL OR LOWER(state) = 'delhi'"))
    bind.execute(sa.text("UPDATE organizations SET region_id = 'delhi' WHERE region_id IS NULL OR LOWER(state) IN ('delhi', 'new delhi')"))
    bind.execute(sa.text("UPDATE organizations SET region_id = 'mumbai_mmr' WHERE LOWER(state) = 'maharashtra'"))


def downgrade():
    op.drop_index("ix_organizations_region_id", table_name="organizations")
    op.drop_column("organizations", "region_id")

    op.drop_index("ix_complaints_region_id", table_name="complaints")
    op.drop_column("complaints", "region_id")

    op.drop_index("ix_atm_locations_region_id", table_name="atm_locations")
    op.drop_column("atm_locations", "region_id")

    op.drop_index("ix_location_clusters_region_id", table_name="location_clusters")
    op.drop_column("location_clusters", "region_id")

    op.drop_index("ix_geography_catalogs_status", table_name="geography_catalogs")
    op.drop_index("ix_geography_catalogs_region_id", table_name="geography_catalogs")
    op.drop_index("ix_geography_catalogs_catalog_id", table_name="geography_catalogs")
    op.drop_index("ix_geography_catalogs_id", table_name="geography_catalogs")
    op.drop_table("geography_catalogs")

    op.drop_index("ix_regions_model_support_status", table_name="regions")
    op.drop_index("ix_regions_state", table_name="regions")
    op.drop_index("ix_regions_id", table_name="regions")
    op.drop_table("regions")
