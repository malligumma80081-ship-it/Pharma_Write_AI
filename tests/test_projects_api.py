from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_user
from app.db.models import Base, Project, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
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

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, test_session
    app.dependency_overrides.clear()
    engine.dispose()


def test_project_endpoints_use_integer_ids(client, authenticated_test_user):
    client, test_session = client
    created = client.post(
        "/api/v1/projects/",
        json={
            "name": "Integer ID project",
            "research_question": "Can projects be fetched using numeric IDs?",
        },
    )

    assert created.status_code == 201
    project_id = created.json()["id"]
    assert isinstance(project_id, int)
    with test_session() as db:
        project = db.get(Project, project_id)
        assert project.owner_id == authenticated_test_user.id

    fetched = client.get(f"/api/v1/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project_id

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "review"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "review"

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_project_id_must_be_an_integer(client):
    client, _ = client
    response = client.get("/api/v1/projects/not-an-integer")

    assert response.status_code == 422


def test_project_creation_requires_authentication(client):
    client, _ = client
    app.dependency_overrides.pop(get_current_user, None)

    response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Protected project",
            "research_question": "Does project creation require login?",
        },
    )

    assert response.status_code == 401


def test_authenticated_user_owns_created_project(client):
    client, test_session = client
    app.dependency_overrides.pop(get_current_user, None)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-owner@gmail.com",
            "password": "a-long-test-password",
        },
    )
    assert registered.status_code == 201, registered.text

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "new-owner@gmail.com",
            "password": "a-long-test-password",
        },
    )
    assert login.status_code == 200, login.text
    access_token = login.json()["access_token"]

    created = client.post(
        "/api/v1/projects/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "Owned project",
            "research_question": "Does the logged-in user own this project?",
        },
    )
    assert created.status_code == 201, created.text

    with test_session() as db:
        project = db.get(Project, created.json()["id"])
        assert str(project.owner_id) == registered.json()["id"]


def test_writer_project_list_only_returns_owned_projects(
    client,
    authenticated_test_user,
):
    client, test_session = client
    own_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "My visible project",
            "research_question": "Is this project listed for its owner?",
        },
    )
    assert own_response.status_code == 201

    other_user = User(
        id=uuid4(),
        email="another-writer@example.test",
        hashed_password="not-used-in-tests",
        role="writer",
        is_active=True,
    )
    with test_session() as db:
        db.add(other_user)
        db.flush()
        db.add(
            Project(
                name="Another writer project",
                research_question="Should another writer see this project?",
                owner_id=other_user.id,
            )
        )
        db.commit()

    response = client.get("/api/v1/projects/")

    assert response.status_code == 200
    assert [project["id"] for project in response.json()] == [
        own_response.json()["id"]
    ]


def test_project_list_requires_authentication(client):
    client, _ = client
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get("/api/v1/projects/")

    assert response.status_code == 401
