import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_verification_code(email: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("Development verification code for %s: %s", email, code)
        return
    message = EmailMessage()
    message["Subject"] = "Campus Share 邮箱验证码"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(f"你的验证码是 {code}，10 分钟内有效。请勿转发。")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)
