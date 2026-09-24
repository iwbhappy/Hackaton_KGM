"""SMTP delivery with mandatory STARTTLS and verified server identity."""
from email.message import EmailMessage
import smtplib
import ssl
from app.notifiers.base import BaseNotifier


class EmailNotifier(BaseNotifier):
    def __init__(self, config):
        self.config = config

    def send(self, subject: str, text: str) -> None:
        """Send UTF-8 mail to explicitly configured recipients."""
        config = self.config
        message = EmailMessage()
        message["Subject"], message["From"], message["To"] = subject, config.smtp_from, config.smtp_to
        message.set_content(text)
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(config.smtp_user, config.smtp_password.get_secret_value())
            refused = smtp.send_message(message)
            if refused:
                raise RuntimeError("Один или несколько адресатов отклонены")
