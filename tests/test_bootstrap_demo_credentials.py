"""Keep public demo bootstrap separate from production authentication state."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.auth.security import get_password_hash, verify_password
from backend.app.models.bootstrap import ensure_prototype_schema
from backend.app.models.models import User


def test_bootstrap_skips_demo_users_when_disabled(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    try:
        ensure_prototype_schema(engine, include_demo_users=False)
        with Session(engine) as db:
            assert db.query(User).count() == 0
    finally:
        engine.dispose()


def test_demo_bootstrap_preserves_existing_password_and_inactive_state(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    try:
        ensure_prototype_schema(engine, include_demo_users=True)
        with Session(engine) as db:
            officer = db.query(User).filter_by(email="state.lea@delhi.cyber.gov.in").one()
            officer.hashed_password = get_password_hash("officer-changed-password-for-test")
            officer.is_active = False
            db.commit()

        ensure_prototype_schema(engine, include_demo_users=True)
        with Session(engine) as db:
            officer = db.query(User).filter_by(email="state.lea@delhi.cyber.gov.in").one()
            assert verify_password("officer-changed-password-for-test", officer.hashed_password)
            assert officer.is_active is False
    finally:
        engine.dispose()
