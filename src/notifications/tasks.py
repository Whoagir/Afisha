# notifications/tasks.py
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from bookings.models import Booking
from events.models import Event
from notifications.models import NotificationLog


@shared_task(queue="fast")
def send_booking_notification(user_id, event_id):
    """Отправляет уведомление о бронировании."""
    # В реальном приложении здесь была бы отправка email/sms/push
    print(f"[NOTIFY] User {user_id} booked event {event_id}")

    # Получаем информацию о событии для сообщения
    try:
        event = Event.objects.get(id=event_id)
        message = (
            f"Вы успешно забронировали место на мероприятие '{event.title}', "
            f"которое состоится {event.start_at.strftime('%d.%m.%Y в %H:%M')}."
        )
    except Event.DoesNotExist:
        message = "Вы успешно забронировали место на мероприятие."

    # Логируем уведомление
    notification = NotificationLog.objects.create(
        user_id=user_id,
        event_id=event_id,
        type=NotificationLog.NotificationType.BOOKING,
        message=message,
        is_sent=True,
        sent_at=timezone.now(),
    )

    return f"Notification {notification.id} sent"


@shared_task(queue="fast")
def send_cancel_notification(user_id, event_id):
    """Отправляет уведомление об отмене бронирования."""
    print(f"[NOTIFY] User {user_id} cancelled booking for event {event_id}")

    # Получаем информацию о событии для сообщения
    try:
        event = Event.objects.get(id=event_id)
        message = (
            f"Вы отменили бронирование на мероприятие '{event.title}', "
            f"которое состоится {event.start_at.strftime('%d.%m.%Y в %H:%M')}."
        )
    except Event.DoesNotExist:
        message = "Вы отменили бронирование на мероприятие."

    notification = NotificationLog.objects.create(
        user_id=user_id,
        event_id=event_id,
        type=NotificationLog.NotificationType.CANCELLATION,
        message=message,
        is_sent=True,
        sent_at=timezone.now(),
    )

    return f"Notification {notification.id} sent"


@shared_task(queue="fast")
def send_reminder(user_id, event_id):
    """Отправляет напоминание о событии."""
    print(f"[NOTIFY] Reminder for user {user_id} about event {event_id}")

    # Получаем информацию о событии для сообщения
    try:
        event = Event.objects.get(id=event_id)
        message = f"Напоминаем, что через час состоится мероприятие '{event.title}' в городе {event.city}."
    except Event.DoesNotExist:
        message = "Напоминаем, что через час состоится мероприятие, на которое вы зарегистрированы."

    notification = NotificationLog.objects.create(
        user_id=user_id,
        event_id=event_id,
        type=NotificationLog.NotificationType.REMINDER,
        message=message,
        is_sent=True,
        sent_at=timezone.now(),
    )

    return f"Notification {notification.id} sent"


@shared_task(queue="fast")
def send_event_cancelled_notification(event_id):
    """Отправляет уведомление об отмене события всем участникам."""
    try:
        event = Event.objects.get(id=event_id)

        # Находим всех пользователей с активными бронированиями
        bookings = Booking.objects.filter(
            event=event, cancelled_at__isnull=True
        ).select_related("user")

        message = (
            f"К сожалению, мероприятие '{event.title}', "
            f"запланированное на {event.start_at.strftime('%d.%m.%Y в %H:%M')}, "
            f"было отменено."
        )

        # Отправляем уведомления всем участникам
        for booking in bookings:
            notification = NotificationLog.objects.create(  # noqa: F841
                user=booking.user,
                event=event,
                type=NotificationLog.NotificationType.EVENT_CANCELLED,
                message=message,
                is_sent=True,
                sent_at=timezone.now(),
            )
            print(
                f"[NOTIFY] User {booking.user.id} notified about event {event.id} cancellation"
            )

        return (
            f"Sent {bookings.count()} cancellation notifications for event {event_id}"
        )

    except Event.DoesNotExist:
        return f"Event {event_id} not found"


@shared_task(queue="slow")
def schedule_reminders():
    """Планирует напоминания за час до начала событий."""
    now = timezone.now()
    one_hour_from_now = now + timedelta(hours=1)
    two_hours_from_now = now + timedelta(hours=2)

    # Находим события, которые начнутся через 1-2 часа
    upcoming_events = Event.objects.filter(
        status=Event.Status.EXPECTED,
        start_at__gt=one_hour_from_now,
        start_at__lte=two_hours_from_now,
    )

    scheduled_count = 0
    for event in upcoming_events:
        # Находим всех пользователей с активными бронированиями
        bookings = event.bookings.filter(cancelled_at__isnull=True)

        for booking in bookings:
            # Планируем отправку напоминания за час до начала
            reminder_time = event.start_at - timedelta(hours=1)
            send_reminder.apply_async(
                args=[booking.user_id, event.id], eta=reminder_time
            )
            scheduled_count += 1

    return f"Scheduled {scheduled_count} reminders for {upcoming_events.count()} events"


@shared_task(queue="slow")
def finish_events():
    """Меняет статус событий на 'завершено', если прошло 2 часа после начала."""
    threshold = timezone.now() - timedelta(hours=2)

    updated = Event.objects.filter(
        status=Event.Status.EXPECTED, start_at__lt=threshold
    ).update(status=Event.Status.FINISHED)

    return f"Updated {updated} events to FINISHED status"
