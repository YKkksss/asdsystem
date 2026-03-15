import json

from django.core.management.base import BaseCommand, CommandError

from apps.notifications.services import (
    get_email_channel_diagnostics,
    send_verification_email,
    send_verification_webhook,
)


class Command(BaseCommand):
    help = "验证真实外部邮件和告警 Webhook 链路是否可用。"

    def add_arguments(self, parser):
        parser.add_argument("--email", dest="email", help="测试邮件接收地址。")
        parser.add_argument("--webhook", dest="webhook", help="测试告警 Webhook 地址。")
        parser.add_argument("--subject", dest="subject", default="ASDSystem 通知链路验证", help="测试主题。")
        parser.add_argument(
            "--message",
            dest="message",
            default="这是一条 ASDSystem 通知链路验证消息。",
            help="测试消息正文。",
        )
        parser.add_argument("--timeout", dest="timeout", type=int, default=5, help="Webhook 请求超时时间，单位秒。")
        parser.add_argument(
            "--webhook-header",
            dest="webhook_headers",
            action="append",
            default=[],
            help="附加 Webhook 请求头，格式为 Key:Value，可重复传入。",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip()
        webhook = (options.get("webhook") or "").strip()
        subject = (options.get("subject") or "").strip() or "ASDSystem 通知链路验证"
        message = (options.get("message") or "").strip() or "这是一条 ASDSystem 通知链路验证消息。"
        timeout = options.get("timeout") or 5

        if not email and not webhook:
            raise CommandError("至少需要提供 --email 或 --webhook 其中一个参数。")

        webhook_headers = self.parse_webhook_headers(options.get("webhook_headers") or [])
        results: dict[str, object] = {}
        failures: list[str] = []

        if email:
            diagnostics = get_email_channel_diagnostics()
            try:
                email_task = send_verification_email(receiver_email=email, subject=subject, content=message)
            except Exception as exc:
                failures.append(f"邮件链路验证失败：{exc}")
                results["email"] = {
                    "status": "failed",
                    "receiver_email": email,
                    "backend": diagnostics["backend"],
                    "issues": diagnostics["issues"],
                    "message": str(exc),
                }
            else:
                results["email"] = {
                    "status": "success",
                    "receiver_email": email,
                    "backend": diagnostics["backend"],
                    "email_task_id": email_task.id,
                    "sent_at": email_task.sent_at.isoformat() if email_task.sent_at else None,
                }

        if webhook:
            try:
                webhook_result = send_verification_webhook(
                    webhook_url=webhook,
                    subject=subject,
                    content=message,
                    timeout=timeout,
                    headers=webhook_headers,
                )
            except Exception as exc:
                failures.append(f"Webhook 链路验证失败：{exc}")
                results["webhook"] = {
                    "status": "failed",
                    "webhook": webhook,
                    "message": str(exc),
                }
            else:
                results["webhook"] = {
                    "status": "success",
                    "webhook": webhook,
                    "status_code": webhook_result["status_code"],
                    "response_text": webhook_result["response_text"],
                }

        self.stdout.write("通知链路验证结果：")
        self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2))

        if failures:
            raise CommandError("；".join(failures))

    @staticmethod
    def parse_webhook_headers(raw_headers: list[str]) -> dict[str, str]:
        parsed_headers: dict[str, str] = {}
        for item in raw_headers:
            if ":" not in item:
                raise CommandError(f"Webhook 请求头格式不正确：{item}")
            key, value = item.split(":", 1)
            header_key = key.strip()
            header_value = value.strip()
            if not header_key or not header_value:
                raise CommandError(f"Webhook 请求头格式不正确：{item}")
            parsed_headers[header_key] = header_value
        return parsed_headers
