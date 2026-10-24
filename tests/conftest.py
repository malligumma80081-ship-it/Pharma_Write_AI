from uuid import UUID

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.main import app


TEST_USER = User(
    id=UUID("d9cb9f04-beba-4bdb-ae8c-3c7200210102"),
    email="project-owner@example.test",
    hashed_password="not-used-in-tests",
    role="writer",
    is_active=True,
)


@pytest.fixture(autouse=True)
def override_current_user_for_api_tests(authenticated_test_user):
    app.dependency_overrides[get_current_user] = lambda: authenticated_test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def authenticated_test_user():
    return TEST_USER
