from django.db import models

from apps.common.models import OperatorStampedModel


class Department(OperatorStampedModel):
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="上级部门",
    )
    dept_code = models.CharField(max_length=64, unique=True, verbose_name="部门编码")
    dept_name = models.CharField(max_length=100, db_index=True, verbose_name="部门名称")
    dept_path = models.CharField(max_length=500, default="/", verbose_name="层级路径")
    dept_level = models.PositiveIntegerField(default=1, verbose_name="层级深度")
    sort_order = models.IntegerField(default=0, verbose_name="排序值")
    approver_user_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="审批负责人",
    )
    status = models.BooleanField(default=True, db_index=True, verbose_name="是否启用")
    remark = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="备注",
    )

    class Meta:
        db_table = "org_department"
        ordering = ["sort_order", "id"]
        verbose_name = "部门"
        verbose_name_plural = "部门"

    def __str__(self) -> str:
        return self.dept_name
