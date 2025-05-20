# events/services/rating.py
from django.db import transaction

from events.models import Event, Rating


class EventNotRatable(Exception):
    """Исключение: событие нельзя оценить"""

    pass


class UserNotAttended(Exception):
    """Исключение: пользователь не посещал событие"""

    pass


class EventNotFound(Exception):
    """Исключение: событие не найдено"""

    pass


@transaction.atomic
def rate_event(user, event, data):
    class InvalidRatingData(Exception):
        """Некорректные данные для оценки"""

        pass

    if event.status != Event.Status.FINISHED:
        raise EventNotRatable()

    if not event.bookings.filter(user=user, cancelled_at__isnull=True).exists():
        raise UserNotAttended()

    defaults = {"score": data.get("score"), "comment": data.get("comment", "")}

    if (
        not Rating.objects.filter(user=user, event=event).exists()
        and "score" not in defaults
    ):
        InvalidRatingData("Score is required for new ratings")

    rating, created = Rating.objects.update_or_create(
        user=user, event=event, defaults=defaults
    )
    return rating
