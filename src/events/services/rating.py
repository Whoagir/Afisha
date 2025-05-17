from django.db import transaction

from events.models import Event, Rating


class EventNotRatable(Exception):
    """Исключение: событие нельзя оценить"""

    pass


class UserNotAttended(Exception):
    """Исключение: пользователь не посещал событие"""

    pass


@transaction.atomic
def rate_event(user, event_id, score, comment=""):
    """
    Оценивает событие пользователем.

    Args:
        user: Пользователь, который оценивает
        event_id: ID события
        score: Оценка (1-5)
        comment: Комментарий к оценке

    Returns:
        Rating: созданная или обновленная оценка

    Raises:
        Event.DoesNotExist: если событие не найдено
        EventNotRatable: если событие еще не завершено
        UserNotAttended: если пользователь не посещал событие
    """
    event = Event.objects.get(id=event_id)

    # Проверяем, что событие завершено
    if event.status != Event.Status.FINISHED:
        raise EventNotRatable("Можно оценивать только завершенные события")

    # Проверяем, что пользователь посещал событие
    attended = event.bookings.filter(user=user, cancelled_at__isnull=True).exists()

    if not attended:
        raise UserNotAttended("Вы не посещали это событие")

    # Создаем или обновляем оценку
    rating, created = Rating.objects.update_or_create(
        user=user, event=event, defaults={"score": score, "comment": comment}
    )

    return rating
