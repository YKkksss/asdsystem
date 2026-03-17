from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.audit.services import record_audit_log
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class AuditModelsUnitTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="AUDIT_UNIT",
            dept_name="审计模型测试部",
        )
        sync_department_hierarchy(self.department)
        self.user = User.objects.create_user(
            username="audit_model_user",
            password="AuditModel12345",
            real_name="审计模型测试用户",
            dept=self.department,
            is_staff=True,
        )

    def test_audit_log_save_should_reject_update(self) -> None:
        audit_log = record_audit_log(
            module_name="AUDIT",
            action_code="AUDIT_MODEL_CREATE",
            description="创建审计日志后禁止修改。",
            user=self.user,
            biz_type="audit_log",
            biz_id=1,
            target_repr="audit-model-test",
        )

        audit_log.description = "尝试修改描述"

        with self.assertRaisesMessage(ValidationError, "审计日志不允许修改。"):
            audit_log.save()

        persisted_audit_log = AuditLog.objects.get(id=audit_log.id)
        self.assertEqual(persisted_audit_log.description, "创建审计日志后禁止修改。")
