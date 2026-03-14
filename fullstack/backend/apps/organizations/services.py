from django.db import transaction

from apps.organizations.models import Department


def _build_department_path(parent: Department | None, department_id: int) -> str:
    if not parent:
        return f"/{department_id}"
    return f"{parent.dept_path}/{department_id}"


def _build_department_level(parent: Department | None) -> int:
    if not parent:
        return 1
    return parent.dept_level + 1


@transaction.atomic
def sync_department_hierarchy(department: Department) -> Department:
    department.dept_level = _build_department_level(department.parent)
    department.dept_path = _build_department_path(department.parent, department.id)
    department.save(update_fields=["dept_level", "dept_path", "updated_at"])

    descendants = department.children.all().select_related("parent")
    for child in descendants:
        sync_department_hierarchy(child)

    return department


def build_department_tree(departments: list[Department]) -> list[dict]:
    children_map: dict[int | None, list[Department]] = {}
    for department in departments:
        children_map.setdefault(department.parent_id, []).append(department)

    def serialize(node: Department) -> dict:
        return {
            "id": node.id,
            "dept_code": node.dept_code,
            "dept_name": node.dept_name,
            "dept_level": node.dept_level,
            "dept_path": node.dept_path,
            "sort_order": node.sort_order,
            "status": node.status,
            "approver_user_id": node.approver_user_id,
            "children": [serialize(child) for child in children_map.get(node.id, [])],
        }

    roots = children_map.get(None, [])
    return [serialize(root) for root in roots]
