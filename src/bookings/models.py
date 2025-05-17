from django.conf import settings
from django.db import models
from django.utils import timezone


class Booking(models.Model):
    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Пользователь",
    )
    event: models.ForeignKey = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Мероприятие",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, verbose_name="Создано"
    )
    cancelled_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, verbose_name="Отменено"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"], name="unique_user_event_booking"
            )
        ]
        indexes = [
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["cancelled_at"]),
        ]
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

    def is_active(self):
        """Проверяет, активно ли бронирование"""
        return self.cancelled_at is None

    def cancel(self):
        """Отменяет бронирование"""
        if not self.cancelled_at:
            self.cancelled_at = timezone.now()
            self.save()
            return True
        return False
