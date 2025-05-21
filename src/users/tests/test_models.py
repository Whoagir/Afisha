from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_create_user_with_unique_email(self):
        """Проверка: создание пользователя с уникальным email"""
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.user.email, "test@example.com")

    def test_cannot_create_user_with_duplicate_email(self):
        """Проверка: невозможность создания пользователя с дублирующимся email"""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                User.objects.create_user(
                    username="anotheruser",
                    email="test@example.com",
                    password="password123",
                )

    def test_str_method(self):
        """Проверка: метод __str__ возвращает username"""
        self.assertEqual(str(self.user), "testuser")

    def test_add_groups_and_permissions(self):
        """Проверка: добавление групп и разрешений"""
        group = Group.objects.create(name="TestGroup")
        permission = Permission.objects.first()  # Берём первое доступное разрешение
        self.user.groups.add(group)
        self.user.user_permissions.add(permission)
        self.assertIn(group, self.user.groups.all())
        self.assertIn(permission, self.user.user_permissions.all())
