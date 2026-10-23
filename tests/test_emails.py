
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from emails import EmailSender


def test_email_rejects_missing_credentials():
    sender = EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username=None,
        password=None,
    )

    with pytest.raises(RuntimeError, match="not configured"):
        sender.send_email(
            subject="Test",
            body="Test email",
            to_emails=["employee@atliq.com"],
        )


def test_email_rejects_invalid_recipient():
    sender = EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username="sender@atliq.com",
        password="test-password",
    )

    with pytest.raises(ValueError, match="valid recipient"):
        sender.send_email(
            subject="Test",
            body="Test email",
            to_emails=["invalid-address"],
        )


def test_email_reports_success_when_smtp_succeeds():
    sender = EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username="sender@atliq.com",
        password="test-password",
    )

    with patch("emails.smtplib.SMTP") as smtp_class:
        smtp = MagicMock()
        smtp_class.return_value.__enter__.return_value = smtp

        result = sender.send_email(
            subject="Test",
            body="Test email",
            to_emails=["employee@atliq.com"],
        )

    assert result["status"] == "sent"
    assert result["recipient_count"] == 1
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with(
        "sender@atliq.com",
        "test-password",
    )
    smtp.send_message.assert_called_once()


def test_email_hides_smtp_error_details():
    sender = EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username="sender@atliq.com",
        password="secret-test-password",
    )

    with patch("emails.smtplib.SMTP") as smtp_class:
        smtp = MagicMock()
        smtp_class.return_value.__enter__.return_value = smtp
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(
            535,
            b"secret-test-password authentication failed",
        )

        with pytest.raises(RuntimeError, match="Email delivery failed") as exc:
            sender.send_email(
                subject="Test",
                body="Test email",
                to_emails=["employee@atliq.com"],
            )

    assert "secret-test-password" not in str(exc.value)
