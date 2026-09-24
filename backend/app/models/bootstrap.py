"""Additive compatibility for prototype databases created before migrations.

Railway can deploy the backend directory alone, where Alembic is not bundled.
This upgrades only explicitly listed nullable columns; it never rebuilds a table,
changes an existing type, deletes rows, or stamps an Alembic revision.
"""
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from backend.app.models.db import Base
from backend.app.models import models  # noqa: F401 -- register metadata


ROLLOUT_COLUMNS = {
    "complaints": ("victim_lat", "victim_lon", "description", "locality", "provenance_mode"),
    "accounts": ("state", "district"),
    "predictions": ("time_model_version", "predicted_minutes_to_cashout", "result_metadata"),
}


def ensure_delhi_auth_users(engine):
    """
    Ensure dedicated Delhi Pilot organizations and users exist and are active,
    and deactivate legacy MP/Indore demo logins.
    """
    from sqlalchemy.orm import Session
    from backend.app.models.models import Organization, User
    from backend.app.auth.security import get_password_hash
    from backend.app.services.geography_catalog_service import ensure_default_regions_and_catalogs

    with Session(engine) as db:
        try:
            ensure_default_regions_and_catalogs(db)
        except Exception:
            pass

        # 1. Organizations
        delhi_nct = db.query(Organization).filter(Organization.name == "Delhi Cyber Crime Unit (NCT)").first()
        if not delhi_nct:
            delhi_nct = Organization(
                name="Delhi Cyber Crime Unit (NCT)",
                org_type="LEA",
                state="Delhi",
                district="ALL",
                region_id="delhi"
            )
            db.add(delhi_nct)
            db.flush()
        else:
            delhi_nct.state = "Delhi"
            delhi_nct.district = "ALL"
            delhi_nct.region_id = "delhi"
            db.flush()

        south_delhi = db.query(Organization).filter(Organization.name == "District Cyber Cell (South Delhi)").first()
        if not south_delhi:
            south_delhi = Organization(
                name="District Cyber Cell (South Delhi)",
                org_type="LEA",
                state="Delhi",
                district="SOUTH",
                region_id="delhi"
            )
            db.add(south_delhi)
            db.flush()
        else:
            south_delhi.state = "Delhi"
            south_delhi.district = "SOUTH"
            south_delhi.region_id = "delhi"
            db.flush()

        # 2. Delhi Users
        state_lea = db.query(User).filter(User.email == "state.lea@delhi.cyber.gov.in").first()
        if not state_lea:
            state_lea = User(
                email="state.lea@delhi.cyber.gov.in",
                hashed_password=get_password_hash("StateLea@2026"),
                full_name="DCP Rajesh Kumar, IPS",
                role="STATE_LEA",
                badge_number="DL-CY-NCT01",
                organization_id=delhi_nct.id,
                is_active=True
            )
            db.add(state_lea)
        else:
            state_lea.organization_id = delhi_nct.id
            state_lea.role = "STATE_LEA"

        dist_lea = db.query(User).filter(User.email == "district.lea@southdelhi.cyber.gov.in").first()
        if not dist_lea:
            dist_lea = User(
                email="district.lea@southdelhi.cyber.gov.in",
                hashed_password=get_password_hash("DistrictLea@2026"),
                full_name="Inspector Amit Sharma",
                role="DISTRICT_LEA",
                badge_number="DL-CY-SD01",
                organization_id=south_delhi.id,
                is_active=True
            )
            db.add(dist_lea)
        else:
            dist_lea.organization_id = south_delhi.id
            dist_lea.role = "DISTRICT_LEA"

        # 3. Deactivate legacy MP/Indore users
        legacy_emails = ["state.lea@mp.police.gov.in", "district.lea@indore.police.gov.in"]
        for legacy_email in legacy_emails:
            legacy_user = db.query(User).filter(User.email == legacy_email).first()
            if legacy_user:
                legacy_user.is_active = False

        db.commit()


def ensure_prototype_schema(engine, *, include_demo_users: bool = True):
    added = []
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(261840912)"))
        Base.metadata.create_all(bind=connection)
        inspector = inspect(connection)
        preparer = connection.dialect.identifier_preparer
        for table_name, column_names in ROLLOUT_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table_name)}
            for name in column_names:
                if name in existing:
                    continue
                column = Base.metadata.tables[table_name].columns.get(name)
                if column is None or not column.nullable:
                    raise RuntimeError(f"Unsupported prototype schema column: {table_name}.{name}")
                ddl = str(CreateColumn(column).compile(dialect=connection.dialect))
                connection.execute(text(f"ALTER TABLE {preparer.quote(table_name)} ADD COLUMN {ddl}"))
                added.append(f"{table_name}.{name}")
    if include_demo_users:
        try:
            ensure_delhi_auth_users(engine)
        except Exception as e:
            print(f"[Bootstrap] Warning: Delhi auth initialization warning: {e}")
    return added

