from django.db.models import Count, Q, Sum

from tag.models import Tag


class GetAllTagsUseCase:
    def execute(self, user, name_icontains=None):
        filters = {}
        if name_icontains:
            filters["name__icontains"] = name_icontains

        tags_query = (
            Tag.objects.filter(**filters, user=user)
            .annotate(
                total_payments=Count(
                    "invoices", filter=Q(invoices__active=True), distinct=True
                ),
                total_value=Sum("invoices__value", filter=Q(invoices__active=True)),
                total_open=Sum("invoices__value_open", filter=Q(invoices__active=True)),
                total_closed=Sum(
                    "invoices__value_closed", filter=Q(invoices__active=True)
                ),
            )
            .order_by("budget", "name")
        )

        return [
            {
                "id": tag.id,
                "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
                "color": tag.color,
                "total_payments": tag.total_payments or 0,
                "total_value": tag.total_value or 0,
                "total_open": tag.total_open or 0,
                "total_closed": tag.total_closed or 0,
                "is_budget": hasattr(tag, "budget"),
            }
            for tag in tags_query
        ]
