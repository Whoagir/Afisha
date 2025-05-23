# events/models.py
from django.conf import settings
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Avg
from django.db.models.signals import post_delete, post_save, pre_save
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
    seats: models.PositiveSmallIntegerField = (
        models.PositiveSmallIntegerField(  # Аннотация добавлена
            verbose_name="Количество мест", validators=[MinValueValidator(1)]
        )
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

    average_rating: models.DecimalField = models.DecimalField(  # Аннотация добавлена
        max_digits=3, decimal_places=2, default=0.0, editable=False
    )
    ratings_count: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0, editable=False
    )

    class Meta:
        ordering = ["status", "start_at"]
        indexes = [
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["city"]),
            models.Index(fields=["organizer"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.title

    def can_be_deleted(self):
        return timezone.now() - self.created_at <= timezone.timedelta(hours=1)

    def is_past(self):
        return self.start_at < timezone.now()

    def get_average_rating(self):
        return self.ratings.aggregate(models.Avg("score"))["score__avg"] or 0


class Rating(models.Model):
    user: models.ForeignKey = models.ForeignKey(  # Аннотация добавлена
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="Пользователь",
    )
    event: models.ForeignKey = models.ForeignKey(  # Аннотация добавлена
        Event,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="Мероприятие",
    )
    score: models.PositiveSmallIntegerField = (
        models.PositiveSmallIntegerField(  # Аннотация добавлена
            validators=[
                MinValueValidator(1),
                MaxValueValidator(10),
            ],
            verbose_name="Оценка",
        )
    )
    comment: models.TextField = models.TextField(  # Аннотация добавлена
        blank=True, verbose_name="Комментарий"
    )
    created_at: models.DateTimeField = models.DateTimeField(  # Аннотация добавлена
        auto_now_add=True, verbose_name="Создано"
    )
    updated_at: models.DateTimeField = models.DateTimeField(  # Аннотация добавлена
        auto_now=True, verbose_name="Обновлено"
    )

    class Meta:
        unique_together = ("user", "event")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "event"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            models.Index(fields=["score"]),
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


@receiver(pre_save, sender=Event)
def cancel_notifications_on_status_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Event.objects.get(pk=instance.pk)
            if (
                old_instance.status == Event.Status.EXPECTED
                and instance.status != Event.Status.EXPECTED
            ):
                from notifications.tasks import cancel_scheduled_notifications

                cancel_scheduled_notifications.delay(instance.pk)
        except Event.DoesNotExist:
            pass


@receiver(post_save, sender=Event)
def update_search_vector(sender, instance, **kwargs):
    Event.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector("title", weight="A")
        + SearchVector("description", weight="B")
    )


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def update_event_rating(sender, instance, **kwargs):
    try:
        with transaction.atomic():
            event = instance.event
            ratings = event.ratings.all()

            event.ratings_count = ratings.count()
            avg = ratings.aggregate(Avg("score"))["score__avg"] or 0
            event.average_rating = round(float(avg), 2)
            event.save(update_fields=["average_rating", "ratings_count"])
    except (Event.DoesNotExist, AttributeError):
        pass
