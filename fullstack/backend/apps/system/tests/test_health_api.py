from django.test import TestCase
from django.urls import reverse


class HealthApiTests(TestCase):
    def test_root_health_returns_success(self) -> None:
        response = self.client.get(reverse("root-health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 200)

    def test_api_health_returns_success(self) -> None:
        response = self.client.get("/api/v1/system/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["service"], "backend")

    def test_api_health_detail_returns_dependency_checks(self) -> None:
        response = self.client.get("/api/v1/system/health/detail/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["checks"]["database"]["status"], "ok")
        self.assertIn(response.json()["data"]["checks"]["redis"]["status"], {"ok", "error"})
        self.assertIn("usage_percent", response.json()["data"]["checks"]["storage"])
