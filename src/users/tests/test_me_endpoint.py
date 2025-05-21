from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class MeEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)
        self.me_url = reverse("user-me")

    def test_get_me(self):
        """Тест получения информации о текущем пользователе"""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["email"], "test@example.com")

    def test_patch_me(self):
        """Тест обновления данных текущего пользователя"""
        data = {
            "email": "updated@example.com",
            "first_name": "Updated",
            "last_name": "Name",
        }
        response = self.client.patch(self.me_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "updated@example.com")
        self.assertEqual(response.data["first_name"], "Updated")
        self.assertEqual(response.data["last_name"], "Name")

    def test_partial_patch_me(self):
        """Тест частичного обновления данных текущего пользователя"""
        data = {"first_name": "Patched"}
        response = self.client.patch(self.me_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Patched")
        self.assertEqual(response.data["last_name"], "User")

    def test_delete_me(self):
        """Тест удаления аккаунта текущего пользователя"""
        response = self.client.delete(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.objects.filter(username="testuser").count(), 0)
