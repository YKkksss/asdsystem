from rest_framework.pagination import PageNumberPagination

from apps.common.response import success_response


class OptionalPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        paginate_flag = (request.query_params.get("paginate") or "").strip().lower()
        should_paginate = paginate_flag in {"1", "true", "yes", "on"} or any(
            key in request.query_params for key in {self.page_query_param, self.page_size_query_param}
        )
        if not should_paginate:
            return None
        return super().paginate_queryset(queryset, request, view=view)

    def build_paginated_payload(self, data):
        page_size = self.get_page_size(self.request) or len(data)
        return {
            "items": data,
            "pagination": {
                "page": self.page.number,
                "page_size": page_size,
                "total": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "has_next": self.page.has_next(),
                "has_previous": self.page.has_previous(),
            },
        }


class OptionalPaginationListMixin:
    pagination_class = OptionalPageNumberPagination

    def build_list_response(self, queryset=None):
        target_queryset = queryset if queryset is not None else self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(target_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return success_response(data=self.paginator.build_paginated_payload(serializer.data))

        serializer = self.get_serializer(target_queryset, many=True)
        return success_response(data=serializer.data)
