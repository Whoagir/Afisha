import logging
import os
import time
from concurrent import futures

import grpc
import notification_pb2
import notification_pb2_grpc
from dotenv import load_dotenv
from email_sender import EmailSender

load_dotenv("../.env")
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class EmailServicer(notification_pb2_grpc.EmailServiceServicer):
    def __init__(self):
        # Валидация обязательных переменных окружения
        required_env_vars = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]
        for var in required_env_vars:
            if not os.getenv(var):
                logger.error(f"Missing required environment variable: {var}")
                raise RuntimeError(f"Missing required environment variable: {var}")

        try:
            self.email_sender = EmailSender(
                smtp_host=os.environ["SMTP_HOST"],
                smtp_port=int(os.environ["SMTP_PORT"]),
                smtp_user=os.environ["SMTP_USER"],
                smtp_password=os.environ["SMTP_PASSWORD"],
            )
            logger.info("Email servicer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize email sender: {str(e)}")
            raise

    def SendEmail(self, request, context):
        logger.info(f"Received email request for {request.recipient_email}")

        try:
            sender_email = request.sender_email or os.getenv("DEFAULT_SENDER")
            if not sender_email:
                logger.error(
                    "Sender email not specified in request and DEFAULT_SENDER not set"
                )
                return notification_pb2.EmailResponse(
                    success=False, message="Sender email not configured"
                )

            success = self.email_sender.send_email(
                recipient_email=request.recipient_email,
                subject=request.subject,
                message=request.message,
                sender_email=sender_email,
            )

            if success:
                logger.info(f"Email sent successfully to {request.recipient_email}")
                return notification_pb2.EmailResponse(
                    success=True, message="Email sent successfully"
                )
            else:
                logger.error(f"Failed to send email to {request.recipient_email}")
                return notification_pb2.EmailResponse(
                    success=False, message="Failed to send email"
                )
        except Exception as e:
            logger.exception(f"Error sending email: {str(e)}")
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
        server.stop(5).wait()  # Graceful shutdown with 5 seconds timeout
        logger.info("Server stopped gracefully")


if __name__ == "__main__":
    serve()
