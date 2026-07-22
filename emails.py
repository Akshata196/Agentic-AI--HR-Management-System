import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional
import mimetypes
import os
from dotenv import load_dotenv

_ = load_dotenv()

class EmailSender:
    def __init__(
        self,
        smtp_server: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send_email(
        self,
        subject: str,
        body: str,
        to_emails: List[str] | str,
        from_email: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[str]] = None,
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email or self.username
        msg["To"] = ", ".join(to_emails) if isinstance(to_emails, list) else to_emails
        msg.set_content(body, subtype="html" if html else "plain")

        if attachments:
            for file_path in attachments:
                if not os.path.isfile(file_path):
                    raise FileNotFoundError(f"Attachment not found: {file_path}")

                mime_type, _ = mimetypes.guess_type(file_path)
                mime_type = mime_type or "application/octet-stream"
                maintype, subtype = mime_type.split("/", 1)

                with open(file_path, "rb") as f:
                    file_data = f.read()
                    filename = os.path.basename(file_path)
                    msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=filename)

        context = ssl.create_default_context()

        if self.use_tls:
          try:
            with smtplib.SMTP(self.smtp_server, self.port, timeout=30) as server:
              server.set_debuglevel(1)

              print("Step 1: Connected to SMTP server")

              server.starttls(context=context)
              print("Step 2: TLS started")

              server.login(self.username, self.password)
              print("Step 3: Login successful")

              print("Step 4: Sending email...")
              server.send_message(msg)

              print("Step 5: Email sent successfully!")

          except Exception as e:
             print("SMTP Error:", e)

        else:
          try:
             with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=30) as server:
                 server.set_debuglevel(1)

             print("Step 1: Connected to SMTP SSL server")

             server.login(self.username, self.password)
             print("Step 2: Login successful")

             print("Step 3: Sending email...")
             server.send_message(msg)

             print("Step 4: Email sent successfully!")

          except Exception as e:
              print("SMTP Error:", e)

if __name__ == "__main__":
    email_sender = EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username=os.getenv("CB_EMAIL"),
        password=os.getenv("CB_EMAIL_PWD"),
        use_tls=True
    )
    email_sender.send_email(
        subject="Test Email",
        body="This is a test email.",
        to_emails="jadhavakshata196@gmail.com",)

