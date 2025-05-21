# src/notifications/grpc_client.py
import logging
import os

import grpc
from django.conf import settings

from notifications.protos import notification_pb2, notification_pb2_grpc

logger = logging.getLogger(__name__)


class EmailClient:
    def __init__(self):
        self.grpc_server = getattr(
            settings,
            "GRPC_EMAIL_SERVER",
            os.environ.get("GRPC_EMAIL_SERVER", "localhost:50051"),
        )
        self.default_sender = getattr(
            settings,
            "DEFAULT_EMAIL_SENDER",
            os.environ.get("DEFAULT_EMAIL_SENDER", "noreply@example.com"),
        )

    def send_email(self, recipient_email, subject, message, **kwargs):
        try:
            with grpc.insecure_channel(self.grpc_server) as channel:
                stub = notification_pb2_grpc.EmailServiceStub(channel)

                # Добавляем метаданные
                metadata = [
                    ("notification_type", kwargs.get("notification_type", "generic")),
                    ("user_id", str(kwargs.get("user_id", 0))),
                    ("event_id", str(kwargs.get("event_id", 0))),
                ]

                request = notification_pb2.EmailRequest(
                    recipient_email=recipient_email,
                    subject=subject,
                    message=message,
                    sender_email=kwargs.get("sender_email", self.default_sender),
                )

                # Передаем метаданные в вызов
                response = stub.SendEmail(request, metadata=metadata)

                if response.success:
                    logger.info(
                        f"Email to {recipient_email} sent successfully via gRPC"
                    )
                    return True
                else:
                    logger.error(f"Failed to send email via gRPC: {response.message}")
                    return False

        except grpc.RpcError as e:
            logger.error(f"gRPC error occurred: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return False


email_client = EmailClient()
