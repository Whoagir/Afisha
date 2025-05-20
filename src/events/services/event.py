# events/services/event.py
from django.db.models import Avg, Count, Q
from django.utils import timezone

from events.models import Event


def get_events_queryset():
    """
    Получает базовый QuerySet событий с аннотациями.
    """
    queryset = Event.objects.all().select_related("organizer").prefetch_related("tags")

    queryset = queryset.annotate(
        active_bookings_count=Count(
            "bookings", filter=Q(bookings__cancelled_at__isnull=True)
        ),
        average_rating=Avg("ratings__score"),
    )

    return queryset


def get_user_upcoming_events(user):
    """
    Получает предстоящие события пользователя.

    Args:
        user: пользователь

    Returns:
        QuerySet с предстоящими событиями пользователя
    """
    now = timezone.now()
    return (
        Event.objects.filter(
            bookings__user=user,
            bookings__cancelled_at__isnull=True,
            start_at__gt=now,
        )
        .select_related("organizer")
        .prefetch_related("tags")
        .order_by("start_at")
    )


def can_delete_event(event):
    return event.can_be_deleted()
