from django.db import migrations


def sync_notification_dispatch_permission(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    SystemPermission = apps.get_model("accounts", "SystemPermission")

    permission, _ = SystemPermission.objects.get_or_create(
        permission_code="button.notification.reminder.dispatch",
        defaults={
            "permission_name": "执行催还扫描",
            "permission_type": "BUTTON",
            "module_name": "notifications",
            "route_path": None,
            "sort_order": 325,
            "status": True,
        },
    )

    permission.permission_name = "执行催还扫描"
    permission.permission_type = "BUTTON"
    permission.module_name = "notifications"
    permission.route_path = None
    permission.sort_order = 325
    permission.status = True
    permission.parent_id = None
    permission.save()

    role_ids = list(Role.objects.filter(role_code__in=["ADMIN", "ARCHIVIST"]).values_list("id", flat=True))
    if not role_ids:
        return

    existing_role_ids = set(
        RolePermission.objects.filter(role_id__in=role_ids, permission_id=permission.id).values_list("role_id", flat=True)
    )
    RolePermission.objects.bulk_create(
        [
            RolePermission(role_id=role_id, permission_id=permission.id)
            for role_id in role_ids
            if role_id not in existing_role_ids
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_notification_dispatch_permission, migrations.RunPython.noop),
    ]
