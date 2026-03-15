from unittest.mock import patch

from django.test import TestCase

from apps.notifications.services import create_email_task, mask_email_address, mask_webhook_url


class NotificationServicesUnitTests(TestCase):
    def test_mask_email_address_should_preserve_minimal_readability(self) -> None:
        self.assertEqual(mask_email_address("ops@example.com"), "o***s@e***e.com")
        self.assertEqual(mask_email_address("a@example.com"), "a***@e***e.com")
        self.assertEqual(mask_email_address("invalid-email"), "***")

    def test_mask_webhook_url_should_hide_host_details_and_path(self) -> None:
        self.assertEqual(
            mask_webhook_url("https://hooks.example.com/api/notify?token=abc"),
            "https://h***s.e***e.com/***",
        )
        self.assertEqual(mask_webhook_url("https://example.com"), "https://e***e.com")
        self.assertEqual(mask_webhook_url("invalid-webhook"), "***")

    @patch("apps.notifications.services.logger.info")
    def test_create_email_task_should_log_masked_receiver_email(self, mocked_logger_info) -> None:
        email_task = create_email_task(
            receiver_user=None,
            receiver_email="ops@example.com",
            subject="通知主题",
            content="通知正文",
            biz_type="unit_test",
            biz_id=1,
        )

        self.assertEqual(email_task.receiver_email, "ops@example.com")
        mocked_logger_info.assert_called_once()
        self.assertEqual(mocked_logger_info.call_args.kwargs["extra"]["receiver_email"], "o***s@e***e.com")
