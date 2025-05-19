# events/tests/py
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from bookings.models import Booking
from events.models import Event, Rating, Tag  # noqa: F401

User = get_user_model()


class EventModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword"
        )

        self.event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            start_at=timezone.now() + timedelta(days=1),
            city="Test City",
            seats=10,
            organizer=self.user,
        )

    def test_event_creation(self):
        self.assertEqual(self.event.title, "Test Event")
        self.assertEqual(self.event.status, Event.Status.EXPECTED)
        self.assertEqual(self.event.organizer, self.user)

    def test_can_be_deleted(self):
        # Новое событие должно быть доступно для удаления
        self.assertTrue(self.event.can_be_deleted())

        # Меняем время создания на более чем час назад
        self.event.created_at = timezone.now() - timedelta(hours=2)
        self.event.save()

        # Теперь событие не должно быть доступно для удаления
        self.assertFalse(self.event.can_be_deleted())


class EventAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword"
        )

        self.client.force_authenticate(user=self.user)

        self.event_data = {
            "title": "Test Event",
            "description": "Test Description",
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "city": "Test City",
            "seats": 10,
            "status": Event.Status.EXPECTED,
        }

    def test_create_event(self):
        url = reverse("event-list")
        response = self.client.post(url, self.event_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Event.objects.get().title, "Test Event")
        self.assertEqual(Event.objects.get().organizer, self.user)

    def test_book_event(self):
        # Создаем событие
        event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            start_at=timezone.now() + timedelta(days=1),
            city="Test City",
            seats=10,
            organizer=self.user,
        )

        # Бронируем место
        url = reverse("event-book", args=[event.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Booking.objects.get().user, self.user)
        self.assertEqual(Booking.objects.get().event, event)

    def test_cancel_booking(self):
        # Создаем событие
        event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            start_at=timezone.now() + timedelta(days=1),
            city="Test City",
            seats=10,
            organizer=self.user,
        )

        # Создаем бронирование
        booking = Booking.objects.create(user=self.user, event=event)

        # Отменяем бронирование
        url = reverse("event-cancel-booking", args=[event.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Проверяем, что бронирование отменено
        booking.refresh_from_db()
        self.assertIsNotNone(booking.cancelled_at)

    def test_my_upcoming_events(self):
        # Создаем два события
        event1 = Event.objects.create(
            title="Test Event 1",
            description="Test Description 1",
            start_at=timezone.now() + timedelta(days=1),
            city="Test City",
            seats=10,
            organizer=self.user,
        )

        event2 = Event.objects.create(
            title="Test Event 2",
            description="Test Description 2",
            start_at=timezone.now() + timedelta(days=2),
            city="Test City",
            seats=10,
            organizer=self.user,
        )

        # Бронируем места на оба события
        Booking.objects.create(user=self.user, event=event1)
        Booking.objects.create(user=self.user, event=event2)

        # Получаем список предстоящих событий
        url = reverse("event-my-upcoming")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_rate_event(self):
        # Создаем завершенное событие
        event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            start_at=timezone.now() - timedelta(days=1),
            city="Test City",
            seats=10,
            organizer=self.user,
            status=Event.Status.FINISHED,
        )

        # Создаем бронирование
        Booking.objects.create(user=self.user, event=event)

        # Оцениваем событие
        url = reverse("event-rate", args=[event.id])
        data = {"score": 5, "comment": "Great event!"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Rating.objects.count(), 1)
        self.assertEqual(Rating.objects.get().score, 5)
        self.assertEqual(Rating.objects.get().comment, "Great event!")
