import os
import smtplib
import ssl
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("CB_EMAIL")
password = os.getenv("CB_EMAIL_PWD")

if not email or not password:
    raise SystemExit("Missing CB_EMAIL or CB_EMAIL_PWD in .env")

try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(email, password)

    print("SMTP authentication successful.")

except Exception as exc:
    print(f"SMTP test failed: {type(exc).__name__}: {exc}")