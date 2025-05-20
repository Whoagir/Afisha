import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, smtp_host, smtp_port, smtp_user, smtp_password):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

        if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
            logger.warning(
                "SMTP configuration is incomplete. Emails will be logged but not sent."
            )

    def send_email(self, recipient_email, subject, message, sender_email):
        """
        Отправляет email получателю.

        Args:
            recipient_email (str): Email получателя
            subject (str): Тема письма
            message (str): Текст письма
            sender_email (str): Email отправителя

        Returns:
            bool: True если письмо отправлено успешно, иначе False
        """
        # Если не настроен SMTP, просто логируем сообщение
        if not all(
            [self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password]
        ):
            logger.info(
                f"Would send email to {recipient_email}, subject: {subject}, message: {message}"
            )
            return True

        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject

            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {recipient_email}")
            return True

        except Exception as e:
            logger.exception(f"Failed to send email: {str(e)}")
            return False
