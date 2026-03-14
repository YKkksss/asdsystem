from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def extract_error_message(detail: Any) -> str | None:
    if isinstance(detail, dict):
        if "detail" in detail:
            return extract_error_message(detail["detail"])

        for value in detail.values():
            message = extract_error_message(value)
            if message:
                return message
        return None

    if isinstance(detail, list):
        for item in detail:
            message = extract_error_message(item)
            if message:
                return message
        return None

    if detail in {None, ""}:
        return None

    return str(detail)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    response = exception_handler(exc, context)

    if response is None:
        return Response(
            {
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "服务器内部错误",
                "data": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    message = extract_error_message(detail) or "请求失败"

    response.data = {
        "code": response.status_code,
        "message": message,
        "data": None,
    }
    return response
