from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.notifications.models import EmailTask, EmailTaskStatus


class VerifyNotificationChannelsCommandTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=465,
        EMAIL_USE_SSL=True,
        EMAIL_USE_TLS=False,
        DEFAULT_FROM_EMAIL="notice@example.com",
    )
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_verify_notification_channels_should_send_email_with_real_smtp_backend(self, mocked_send_mail) -> None:
        stdout = StringIO()

        call_command(
            "verify_notification_channels",
            email="ops@example.com",
            subject="链路验证主题",
            message="链路验证正文",
            stdout=stdout,
        )

        self.assertEqual(EmailTask.objects.count(), 1)
        email_task = EmailTask.objects.get()
        self.assertEqual(email_task.send_status, EmailTaskStatus.SUCCESS)
        self.assertEqual(email_task.receiver_email, "ops@example.com")
        self.assertIn('"status": "success"', stdout.getvalue())
        self.assertIn('"receiver_email": "o***s@e***e.com"', stdout.getvalue())
        self.assertNotIn('"receiver_email": "ops@example.com"', stdout.getvalue())
        mocked_send_mail.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_verify_notification_channels_should_reject_local_only_email_backend(self) -> None:
        with self.assertRaises(CommandError) as context:
            call_command("verify_notification_channels", email="ops@example.com")

        self.assertIn("本地调试", str(context.exception))

    @patch("apps.notifications.services.urlopen")
    def test_verify_notification_channels_should_send_webhook(self, mocked_urlopen) -> None:
        mocked_response = MagicMock()
        mocked_response.getcode.return_value = 200
        mocked_response.read.return_value = b"ok"
        mocked_urlopen.return_value.__enter__.return_value = mocked_response

        stdout = StringIO()
        call_command(
            "verify_notification_channels",
            webhook="https://example.com/webhook",
            subject="Webhook 验证",
            message="Webhook 正文",
            stdout=stdout,
        )

        self.assertIn('"status": "success"', stdout.getvalue())
        self.assertIn('"webhook": "https://e***e.com/***"', stdout.getvalue())
        self.assertNotIn('"webhook": "https://example.com/webhook"', stdout.getvalue())
        self.assertIn('"status_code": 200', stdout.getvalue())
