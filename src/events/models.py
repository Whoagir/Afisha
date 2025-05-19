# events/models.py
from django.conf import settings
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Event(models.Model):
    class Status(models.TextChoices):
        EXPECTED = "expected", "Ожидается"
        CANCELLED = "cancelled", "Отменено"
        FINISHED = "finished", "Завершено"

    title: models.CharField = models.CharField(max_length=255, verbose_name="Название")
    description: models.TextField = models.TextField(verbose_name="Описание")
    start_at: models.DateTimeField = models.DateTimeField(verbose_name="Время начала")
    city: models.CharField = models.CharField(max_length=100, verbose_name="Город")
    seats: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(
        verbose_name="Количество мест"
    )
    status: models.CharField = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.EXPECTED,
        db_index=True,
        verbose_name="Статус",
    )
    organizer: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_events",
        verbose_name="Организатор",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, verbose_name="Создано"
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        auto_now=True, verbose_name="Обновлено"
    )
    tags: models.ManyToManyField = models.ManyToManyField(
        "Tag", related_name="events", blank=True, verbose_name="Теги"
    )
    search_vector: SearchVectorField = SearchVectorField(null=True, blank=True)

    class Meta:
        ordering = ["status", "start_at"]
        indexes = [
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["city"]),
            models.Index(fields=["organizer"]),
        ]
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.title

    def can_be_deleted(self):
        """Проверяет, можно ли удалить событие (в течение 1 часа после создания)"""
        return timezone.now() - self.created_at <= timezone.timedelta(hours=1)

    def is_past(self):
        """Проверяет, прошло ли событие"""
        return self.start_at < timezone.now()

    def get_average_rating(self):
        """Получает среднюю оценку события"""
        return self.ratings.aggregate(models.Avg("score"))["score__avg"] or 0


class Rating(models.Model):
    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="Пользователь",
    )
    event: models.ForeignKey = models.ForeignKey(
        "Event",
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="Мероприятие",
    )
    score: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Оценка"
    )
    comment: models.TextField = models.TextField(blank=True, verbose_name="Комментарий")
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, verbose_name="Создано"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"], name="unique_user_event_rating"
            )
        ]
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"

    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.score})"


class Tag(models.Model):
    name: models.CharField = models.CharField(
        max_length=50, unique=True, verbose_name="Название"
    )
    slug: models.SlugField = models.SlugField(
        max_length=50, unique=True, verbose_name="Slug"
    )

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
        ]
        verbose_name = "Тег"
        verbose_name_plural = "Теги"


@receiver(post_save, sender=Event)
def update_search_vector(sender, instance, **kwargs):
    """Обновляет поле search_vector при сохранении события"""
    Event.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector("title", weight="A")
        + SearchVector("description", weight="B")
    )
