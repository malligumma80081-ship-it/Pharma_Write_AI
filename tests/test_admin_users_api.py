import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_user
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as db:
            yield db

    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="not-used-in-test",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin

    try:
        with test_session() as db:
            db.add(admin)
            db.add(
                User(
                    id=uuid.uuid4(),
                    email="writer@example.com",
                    hashed_password="not-used-in-test",
                    role="writer",
                    requested_role="project_manager",
                    is_active=True,
                )
            )
            db.commit()
        with TestClient(app) as client:
            yield client, test_session, admin
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_registration_role_request_does_not_grant_privileges(api_client):
    client, test_session, _ = api_client

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "secure-test-password",
            "requested_role": "reviewer",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "writer"
    assert response.json()["requested_role"] == "reviewer"

    with test_session() as db:
        user = db.query(User).filter_by(email="new-user@example.com").one()
        assert user.role == "writer"
        assert user.requested_role == "reviewer"


def test_registration_cannot_grant_or_request_admin_role(api_client):
    client, test_session, _ = api_client

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "self-appointed-admin@example.com",
            "password": "secure-test-password",
            "requested_role": "admin",
        },
    )

    assert response.status_code == 422
    with test_session() as db:
        user = db.query(User).filter_by(
            email="self-appointed-admin@example.com"
        ).first()
        assert user is None


def test_admin_can_list_users_and_assign_requested_role(api_client):
    client, test_session, _ = api_client

    users_response = client.get("/api/v1/admin/users")
    assert users_response.status_code == 200
    requested_user = next(
        user
        for user in users_response.json()
        if user["email"] == "writer@example.com"
    )
    assert requested_user["requested_role"] == "project_manager"

    updated = client.patch(
        f"/api/v1/admin/users/{requested_user['id']}/role",
        json={"role": "project_manager"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "project_manager"
    assert updated.json()["requested_role"] is None

    with test_session() as db:
        user = db.query(User).filter_by(email="writer@example.com").one()
        assert user.role == "project_manager"
        assert user.requested_role is None


def test_admin_cannot_remove_own_admin_role(api_client):
    client, _, admin = api_client

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/role",
        json={"role": "writer"},
    )

    assert response.status_code == 409


def test_non_admin_cannot_manage_user_roles(api_client):
    client, _, _ = api_client
    writer = User(
        id=uuid.uuid4(),
        email="not-admin@example.com",
        hashed_password="not-used-in-test",
        role="writer",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: writer

    assert client.get("/api/v1/admin/users").status_code == 403
