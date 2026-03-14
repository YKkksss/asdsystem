from typing import Any

from rest_framework.response import Response


def success_response(data: Any = None, message: str = "操作成功", code: int = 200) -> Response:
    return Response(
        {
            "code": code,
            "message": message,
            "data": data,
        },
        status=code,
    )


def error_response(message: str, code: int, data: Any = None) -> Response:
    return Response(
        {
            "code": code,
            "message": message,
            "data": data,
        },
        status=code,
    )
