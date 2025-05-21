# email_notofication/server.py
import logging
import os
import time
from concurrent import futures

import django
import grpc
import notification_pb2
import notification_pb2_grpc
from dotenv import load_dotenv

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.afisha.settings")  # noqa: F402

# Инициализируем Django
django.setup()  # noqa: F402

from src.notifications.tasks import send_booking_notification  # noqa: E402
from src.notifications.tasks import send_cancel_notification  # noqa: E402
from src.notifications.tasks import send_event_cancelled_notification  # noqa: E402
from src.notifications.tasks import send_reminder  # noqa: E402

load_dotenv("../.env")
logger = logging.getLogger(__name__)


class EmailServicer(notification_pb2_grpc.EmailServiceServicer):
    def SendEmail(self, request, context):
        logger.info(f"Received email request for {request.recipient_email}")

        try:
            # Определяем тип уведомления из метаданных
            metadata = dict(context.invocation_metadata())
            notification_type = metadata.get("notification_type", "generic")

            # Ставим задачу в Celery в зависимости от типа
            if notification_type == "booking":
                send_booking_notification.delay(
                    user_id=int(metadata["user_id"]), event_id=int(metadata["event_id"])
                )
            elif notification_type == "cancellation":
                send_cancel_notification.delay(
                    user_id=int(metadata["user_id"]), event_id=int(metadata["event_id"])
                )
            elif notification_type == "reminder":
                send_reminder.delay(
                    user_id=int(metadata["user_id"]), event_id=int(metadata["event_id"])
                )
            elif notification_type == "event_cancelled":
                send_event_cancelled_notification.delay(
                    event_id=int(metadata["event_id"])
                )
            else:
                return notification_pb2.EmailResponse(
                    success=False,
                    message=f"Unsupported notification type: {notification_type}",
                )

            return notification_pb2.EmailResponse(
                success=True, message="Notification task queued successfully"
            )

        except KeyError as e:
            logger.error(f"Missing metadata: {str(e)}")
            return notification_pb2.EmailResponse(
                success=False, message=f"Missing required metadata: {str(e)}"
            )
        except Exception as e:
            logger.exception(f"Error queuing task: {str(e)}")
            return notification_pb2.EmailResponse(
                success=False, message=f"Internal server error: {str(e)}"
            )


def serve():
    # Проверка порта
    try:
        port = int(os.getenv("GRPC_PORT", "50051"))
    except ValueError:
        logger.error("Invalid GRPC_PORT value, must be integer")
        port = 50051

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    notification_pb2_grpc.add_EmailServiceServicer_to_server(EmailServicer(), server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()

    logger.info(f"Email notification service started on port {port}")

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(5).wait()
        logger.info("Server stopped gracefully")


if __name__ == "__main__":
    serve()
