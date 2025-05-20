# events/services/booking.py
from django.db import transaction
from django.db.models import Count, Q  # noqa: F401
from django.utils import timezone

from bookings.models import Booking
from events.models import Event
from notifications.tasks import send_booking_notification, send_cancel_notification


class NoSeats(Exception):
    """Исключение: нет свободных мест"""

    pass


class EventNotFound(Exception):
    """Исключение: событие не найдено"""

    pass


class BookingNotFound(Exception):
    """Исключение: бронирование не найдено"""

    pass


class EventFinished(Exception):
    """Исключение: событие уже завершено"""

    pass


@transaction.atomic
def create_booking(user, event_id):
    """
    Создает бронирование для пользователя на указанное событие.

    Args:
        user: Пользователь, который бронирует
        event_id: ID события

    Returns:
        Booking: созданное бронирование

    Raises:
        EventNotFound: если событие не найдено
        NoSeats: если нет свободных мест
        EventFinished: если событие уже завершено
    """
    try:
        event = Event.objects.select_for_update().get(id=event_id)
    except Event.DoesNotExist:
        raise EventNotFound("Событие не найдено")

    if event.status != Event.Status.EXPECTED:
        raise EventFinished("Событие уже завершено или отменено")

    if event.start_at <= timezone.now():
        raise EventFinished("Событие уже началось")

    active_bookings_count = Booking.objects.filter(
        event=event, cancelled_at__isnull=True
    ).count()

    if active_bookings_count >= event.seats:
        raise NoSeats("Нет свободных мест")

    booking, created = Booking.objects.get_or_create(
        user=user, event=event, defaults={"cancelled_at": None}
    )

    if not created and booking.cancelled_at:
        booking.cancelled_at = None
        booking.save(update_fields=["cancelled_at"])

    if created or (not booking.cancelled_at):
        send_booking_notification.delay(user.id, event.id)

    return booking


@transaction.atomic
def cancel_booking(user, event_id):
    """
    Отменяет бронирование пользователя на указанное событие.

    Args:
        user: Пользователь, который отменяет бронирование
        event_id: ID события

    Returns:
        Booking: отмененное бронирование

    Raises:
        BookingNotFound: если бронирование не найдено
    """
    try:
        booking = Booking.objects.get(
            user=user, event_id=event_id, cancelled_at__isnull=True
        )
    except Booking.DoesNotExist:
        raise BookingNotFound("Бронирование не найдено или уже отменено")

    booking.cancel()

    send_cancel_notification.delay(user.id, event_id)

    return booking
