"""SMTP email adapter. Failures are propagated to callers; secrets are never logged."""
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    def __init__(self, smtp_server: str, port: int, username: Optional[str], password: Optional[str], use_tls: bool = True):
        self.smtp_server, self.port = smtp_server, port
        self.username, self.password = username, password
        self.use_tls = use_tls

    def send_email(self, subject: str, body: str, to_emails: List[str] | str,
                   from_email: Optional[str] = None, html: bool = False,
                   attachments: Optional[List[str]] = None) -> dict:
        if not self.username or not self.password:
            raise RuntimeError("Email is not configured. Set CB_EMAIL and CB_EMAIL_PWD in your local .env file.")
        recipients = to_emails if isinstance(to_emails, list) else [to_emails]
        if not recipients or any("@" not in address for address in recipients):
            raise ValueError("At least one valid recipient email address is required.")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email or self.username
        msg["To"] = ", ".join(recipients)
        msg.set_content(body, subtype="html" if html else "plain")
        for file_path in attachments or []:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"Attachment not found: {file_path}")
            mime_type, _ = mimetypes.guess_type(file_path)
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            with open(file_path, "rb") as stream:
                msg.add_attachment(stream.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(file_path))
        context = ssl.create_default_context()
        try:
            if self.use_tls:
                with smtplib.SMTP(self.smtp_server, self.port, timeout=30) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=30) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise RuntimeError(f"Email delivery failed: {type(exc).__name__}") from exc
        return {"status": "sent", "recipient_count": len(recipients), "subject": subject}
