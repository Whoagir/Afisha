# src/users/tests/conftest.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="adminpass"
    )


@pytest.fixture
def regular_user():
    return User.objects.create_user(
        username="user", email="user@example.com", password="userpass"
    )
