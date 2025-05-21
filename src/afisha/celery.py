# src/afisha/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "afisha.settings")
broker_connection_retry_on_startup = True
app = Celery("afisha")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(["bookings", "events", "notifications", "users"])
# Настройка очередей
app.conf.task_routes = {
    "notifications.tasks.send_booking_notification": {"queue": "fast"},
    "notifications.tasks.send_cancel_notification": {"queue": "fast"},
    "notifications.tasks.send_reminder": {"queue": "fast"},
    "notifications.tasks.send_event_cancelled_notification": {"queue": "fast"},
    "notifications.tasks.schedule_reminders": {"queue": "slow"},
    "notifications.tasks.finish_events": {"queue": "slow"},
    "*": {"queue": "slow"},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
