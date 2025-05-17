from django.conf import settings
from django.db import models
from django.utils import timezone  # noqa: F401


class NotificationLog(models.Model):
    class NotificationType(models.TextChoices):
        BOOKING = "booking", "Бронирование"
        CANCELLATION = "cancellation", "Отмена"
        REMINDER = "reminder", "Напоминание"
        EVENT_CANCELLED = "event_cancelled", "Мероприятие отменено"

    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    event: models.ForeignKey = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Мероприятие",
    )
    type: models.CharField = models.CharField(
        max_length=15, choices=NotificationType.choices, verbose_name="Тип уведомления"
    )
    message: models.TextField = models.TextField(blank=True, verbose_name="Сообщение")
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, verbose_name="Создано"
    )
    is_sent: models.BooleanField = models.BooleanField(
        default=False, verbose_name="Отправлено"
    )
    sent_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, verbose_name="Время отправки"
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_sent"]),
            models.Index(fields=["event", "type"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return f"{self.get_type_display()} для {self.user.username}"
