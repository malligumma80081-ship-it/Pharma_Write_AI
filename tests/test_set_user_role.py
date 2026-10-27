import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import User
from scripts.set_user_role import set_user_role


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    User.__table__.create(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_set_user_role_promotes_existing_account(db_session):
    user = User(
        email="teamlead@example.com",
        hashed_password="not-used-in-test",
        role="writer",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    updated = set_user_role(db_session, " TEAMLEAD@example.com ", "reviewer")

    assert updated.role == "reviewer"
    assert db_session.get(User, user.id).role == "reviewer"


def test_set_user_role_uses_team_leader_label(db_session):
    user = User(
        email="teamlead@example.com",
        hashed_password="not-used-in-test",
        role="writer",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    updated = set_user_role(db_session, user.email, "team_leader")

    assert updated.role == "reviewer"


def test_set_user_role_assigns_project_manager(db_session):
    user = User(
        email="manager@example.com",
        hashed_password="not-used-in-test",
        role="writer",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    updated = set_user_role(db_session, user.email, "project_manager")

    assert updated.role == "project_manager"


def test_set_user_role_rejects_unknown_role(db_session):
    with pytest.raises(ValueError, match="Role must be"):
        set_user_role(db_session, "teamlead@example.com", "owner")


def test_set_user_role_rejects_unknown_account(db_session):
    with pytest.raises(ValueError, match="No account found"):
        set_user_role(db_session, "missing@example.com", "reviewer")
