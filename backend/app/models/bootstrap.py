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


def ensure_prototype_schema(engine):
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
    return added
