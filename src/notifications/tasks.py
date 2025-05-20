# notifications/tasks.py
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from bookings.models import Booking
from events.models import Event
from notifications.grpc_client import email_client
from notifications.models import NotificationLog

User = get_user_model()


def _send_notification(
    user_id, event_id, notification_type, subject_template, message_template
):
    """Вспомогательная функция для отправки уведомлений."""
    try:
        user = User.objects.get(id=user_id)
        event = Event.objects.get(id=event_id)

        subject = subject_template.format(event_title=event.title)
        message = message_template.format(
            event_title=event.title,
            start_at=event.start_at.strftime("%d.%m.%Y в %H:%M"),
            city=event.city,
        )

        success = email_client.send_email(
            recipient_email=user.email, subject=subject, message=message
        )
        error_message = None

    except Event.DoesNotExist as e:
        success = False
        error_message = f"Event not found: {str(e)}"
        message = "Информация о мероприятии недоступна"
    except User.DoesNotExist as e:
        success = False
        error_message = f"User not found: {str(e)}"
        message = "Пользователь не найден"
    except Exception as e:
        success = False
        error_message = f"Unexpected error: {str(e)}"
        message = "Произошла ошибка при отправке уведомления"

    notification = NotificationLog.objects.create(
        user_id=user_id,
        event_id=event_id,
        type=notification_type,
        message=message,
        is_sent=success,
        sent_at=timezone.now() if success else None,
        error_message=error_message,
    )

    return notification, success


@shared_task(queue="fast")
def send_booking_notification(user_id, event_id):
    """Отправляет уведомление о бронировании."""
    notification, success = _send_notification(
        user_id=user_id,
        event_id=event_id,
        notification_type=NotificationLog.NotificationType.BOOKING,
        subject_template="Бронирование мероприятия: {event_title}",
        message_template=(
            "Вы успешно забронировали место на мероприятие '{event_title}', "
            "которое состоится {start_at}."
        ),
    )
    return f"Booking notification {notification.id} sent: {success}"


@shared_task(queue="fast")
def send_cancel_notification(user_id, event_id):
    """Отправляет уведомление об отмене бронирования."""
    notification, success = _send_notification(
        user_id=user_id,
        event_id=event_id,
        notification_type=NotificationLog.NotificationType.CANCELLATION,
        subject_template="Отмена бронирования: {event_title}",
        message_template=(
            "Вы отменили бронирование на мероприятие '{event_title}', "
            "которое должно было состояться {start_at}."
        ),
    )
    return f"Cancellation notification {notification.id} sent: {success}"


@shared_task(queue="fast")
def send_reminder(user_id, event_id):
    """Отправляет напоминание о событии."""
    try:
        # Проверяем статус события перед отправкой
        event = Event.objects.get(id=event_id)
        if event.status != Event.Status.EXPECTED:
            return f"Reminder for event {event_id} cancelled - event is {event.status}"

        notification, success = _send_notification(
            user_id=user_id,
            event_id=event_id,
            notification_type=NotificationLog.NotificationType.REMINDER,
            subject_template="Напоминание: {event_title}",
            message_template=(
                "Напоминаем, что через час состоится мероприятие '{event_title}' "
                "в городе {city}."
            ),
        )
        return f"Reminder {notification.id} sent: {success}"
    except Event.DoesNotExist:
        return f"Reminder cancelled - event {event_id} does not exist"


@shared_task(queue="fast")
def send_event_cancelled_notification(event_id):
    """Отправляет уведомление об отмене события всем участникам."""
    try:
        event = Event.objects.get(id=event_id)
        bookings = Booking.objects.filter(
            event=event, cancelled_at__isnull=True
        ).select_related("user")

        results = []
        for booking in bookings:
            notification, success = _send_notification(
                user_id=booking.user_id,
                event_id=event_id,
                notification_type=NotificationLog.NotificationType.EVENT_CANCELLED,
                subject_template="Отмена мероприятия: {event_title}",
                message_template=(
                    "К сожалению, мероприятие '{event_title}', "
                    "запланированное на {start_at}, было отменено."
                ),
            )
            results.append(success)

        success_count = sum(results)
        fail_count = len(results) - success_count
        return (
            f"Sent {success_count} successful and {fail_count} failed "
            f"notifications for event {event_id}"
        )

    except Event.DoesNotExist:
        return f"Event {event_id} not found"


@shared_task(queue="slow")
def schedule_reminders():
    """Планирует напоминания за час до начала событий."""
    now = timezone.now()
    # Находим события, которые начнутся через 1-2 часа
    events = Event.objects.filter(
        status=Event.Status.EXPECTED,
        start_at__range=(now + timedelta(hours=1), now + timedelta(hours=2)),
    )

    scheduled = []
    for event in events:
        # Проверяем, не запланированы ли уже уведомления для этого события
        existing_notifications = NotificationLog.objects.filter(
            event=event,
            type=NotificationLog.NotificationType.REMINDER,
            created_at__gte=now - timedelta(hours=24),  # Проверяем за последние 24 часа
        ).exists()

        if not existing_notifications:
            for booking in event.bookings.filter(cancelled_at__isnull=True):
                # Точно рассчитываем время отправки - ровно за час до начала
                eta = event.start_at - timedelta(hours=1)
                if eta > now:  # Проверяем, что время отправки в будущем
                    send_reminder.apply_async(args=[booking.user_id, event.id], eta=eta)
                    scheduled.append(booking.id)

    return f"Scheduled {len(scheduled)} reminders for {events.count()} events"


@shared_task(queue="fast")
def cancel_scheduled_notifications(event_id):
    """Отменяет все запланированные уведомления для события."""
    # В реальных условиях здесь был бы код для отмены задач в Celery
    # Но поскольку прямая отмена задач сложна, мы добавляем проверку статуса
    # в сами задачи отправки уведомлений
    return f"Notification cancellation registered for event {event_id}"


@shared_task(queue="slow")
def finish_events():
    """Меняет статус событий на 'завершено' через 2 часа после начала."""
    updated = Event.objects.filter(
        status=Event.Status.EXPECTED, start_at__lt=timezone.now() - timedelta(hours=2)
    ).update(status=Event.Status.FINISHED)

    return f"Updated {updated} events to FINISHED status"
