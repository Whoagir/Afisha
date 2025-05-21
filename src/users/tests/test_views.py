from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


class UserViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )
        self.regular_user = User.objects.create_user(
            username="user", email="user@example.com", password="userpass"
        )
        self.client.force_authenticate(user=self.admin_user)  # Логинимся как админ

    def test_register_user(self):
        """Проверка: регистрация нового пользователя"""
        url = reverse("user-list")
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "password_confirm": "password123",
        }
        self.client.logout()  # Регистрация доступна без авторизации
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(User.objects.count(), 3)

    def test_list_users_as_admin(self):
        """Проверка: админ видит всех пользователей"""
        url = reverse("user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data["results"]), 2
        )  # Админ и обычный пользователь

    def test_list_users_as_regular_user(self):
        """Проверка: обычный пользователь не имеет доступа к списку пользователей"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_user(self):
        """Проверка: получение информации о пользователе"""
        url = reverse("user-detail", kwargs={"pk": self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "user")

    def test_me_patch(self):
        """Проверка: частичное обновление текущего пользователя"""
        url = reverse("user-me")
        data = {"first_name": "AdminUpdated"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.first_name, "AdminUpdated")

    def test_delete_user(self):
        """Проверка: удаление пользователя"""
        url = reverse("user-detail", kwargs={"pk": self.regular_user.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.objects.count(), 1)

    def test_me_get(self):
        """Проверка: получение информации о текущем пользователе"""
        url = reverse("user-me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "admin")

    def test_me_delete(self):
        """Проверка: удаление текущего пользователя"""
        url = reverse("user-me")
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.objects.count(), 1)

    @patch("events.services.event.get_user_upcoming_events")
    def test_upcoming_events(self, mock_get_events):
        """Проверка: получение предстоящих мероприятий с использованием мока"""
        # Создаем мок-объект события
        mock_event = Mock()
        mock_event.title = "TestEvent"
        mock_event.organizer = self.regular_user
        mock_event.tags = Mock()

        # Настраиваем мок-функцию и возвращаемые данные
        mock_queryset = Mock()
        mock_queryset.select_related.return_value = mock_queryset
        mock_queryset.prefetch_related.return_value = mock_queryset

        # Настраиваем пагинацию
        mock_queryset.__getitem__.return_value = [mock_event]
        mock_queryset.count.return_value = 1

        mock_get_events.return_value = mock_queryset

        url = reverse("user-upcoming-events", kwargs={"pk": self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Проверяем, что в ответе есть результаты
        self.assertIn("results", response.data)

    def test_custom_token_obtain_pair(self):
        """Проверка: получение токенов"""
        url = reverse("token_obtain_pair")
        data = {"username": "admin", "password": "adminpass"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_custom_token_refresh(self):
        """Проверка: обновление токена"""
        # Получаем токены
        url = reverse("token_obtain_pair")
        data = {"username": "admin", "password": "adminpass"}
        response = self.client.post(url, data, format="json")
        refresh_token = response.data["refresh"]

        # Обновляем токен
        url = reverse("token_refresh")
        response = self.client.post(url, {"refresh": refresh_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
