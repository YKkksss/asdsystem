from django.db import migrations


def sync_system_health_detail_permission(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    SystemPermission = apps.get_model("accounts", "SystemPermission")

    permission, _ = SystemPermission.objects.get_or_create(
        permission_code="button.system.health.detail",
        defaults={
            "permission_name": "查看系统健康详情",
            "permission_type": "BUTTON",
            "module_name": "system",
            "route_path": None,
            "sort_order": 395,
            "status": True,
        },
    )

    permission.permission_name = "查看系统健康详情"
    permission.permission_type = "BUTTON"
    permission.module_name = "system"
    permission.route_path = None
    permission.sort_order = 395
    permission.status = True
    permission.parent_id = None
    permission.save()

    admin_role_ids = list(Role.objects.filter(role_code="ADMIN").values_list("id", flat=True))
    if not admin_role_ids:
        return

    existing_role_ids = set(
        RolePermission.objects.filter(role_id__in=admin_role_ids, permission_id=permission.id).values_list("role_id", flat=True)
    )
    RolePermission.objects.bulk_create(
        [
            RolePermission(role_id=role_id, permission_id=permission.id)
            for role_id in admin_role_ids
            if role_id not in existing_role_ids
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_sync_notification_dispatch_permission"),
    ]

    operations = [
        migrations.RunPython(sync_system_health_detail_permission, migrations.RunPython.noop),
    ]
