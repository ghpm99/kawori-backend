from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from audit.ai_assist import build_audit_ai_insights
from audit.application.use_cases.get_audit_logs import GetAuditLogsUseCase
from audit.application.use_cases.get_audit_stats import GetAuditStatsUseCase
from audit.interfaces.api.serializers.audit_logs_serializers import (
    AuditLogsResponseSerializer,
)
from audit.interfaces.api.serializers.audit_stats_serializers import (
    AuditStatsResponseSerializer,
)
from audit.models import AuditLog
from kawori.decorators import validate_user
from kawori.utils import format_date, paginate


@require_GET
@validate_user("admin")
def get_audit_logs(request, user):
    payload, status_code = GetAuditLogsUseCase().execute(
        request_get=request.GET,
        audit_log_model=AuditLog,
        format_date_fn=format_date,
        paginate_fn=paginate,
        timedelta_cls=timedelta,
    )
    serializer = AuditLogsResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def get_audit_stats(request, user):
    payload, status_code = GetAuditStatsUseCase().execute(
        audit_log_model=AuditLog,
        now_fn=timezone.now,
        timedelta_cls=timedelta,
        count_cls=Count,
    )
    serializer = AuditStatsResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def get_audit_report(request, user):
    req = request.GET
    filters = {}
    response_filters = {}

    if req.get("category"):
        filters["category"] = req.get("category")
        response_filters["category"] = req.get("category")
    if req.get("action"):
        filters["action"] = req.get("action")
        response_filters["action"] = req.get("action")
    if req.get("result"):
        filters["result"] = req.get("result")
        response_filters["result"] = req.get("result")
    if req.get("user_id"):
        filters["user_id"] = req.get("user_id")
        response_filters["user_id"] = req.get("user_id")
    if req.get("username"):
        filters["username__icontains"] = req.get("username")
        response_filters["username"] = req.get("username")
    if req.get("date_from"):
        date_from = format_date(req.get("date_from"))
        if date_from:
            filters["created_at__gte"] = date_from
            response_filters["date_from"] = req.get("date_from")
    if req.get("date_to"):
        date_to = format_date(req.get("date_to"))
        if date_to:
            filters["created_at__lte"] = date_to + timedelta(days=1)
            response_filters["date_to"] = req.get("date_to")

    limit = int(req.get("limit", 10))
    if limit < 1:
        limit = 10
    if limit > 100:
        limit = 100

    logs = AuditLog.objects.filter(**filters)

    summary = {
        "total_events": logs.count(),
        "unique_users": logs.exclude(username="").values("username").distinct().count(),
        "success_events": logs.filter(result="success").count(),
        "failure_events": logs.filter(result="failure").count(),
        "error_events": logs.filter(result="error").count(),
    }

    interactions_by_day = list(
        logs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    interactions_by_day = [
        {
            "day": item["day"].isoformat() if item["day"] else None,
            "count": item["count"],
        }
        for item in interactions_by_day
    ]

    by_action = list(
        logs.values("action")
        .annotate(count=Count("id"))
        .order_by("-count", "action")[:limit]
    )
    by_category = list(
        logs.values("category")
        .annotate(count=Count("id"))
        .order_by("-count", "category")[:limit]
    )
    by_user = list(
        logs.exclude(username="")
        .values("username", "user_id")
        .annotate(count=Count("id"))
        .order_by("-count", "username")[:limit]
    )
    failures_by_action = list(
        logs.filter(result__in=["failure", "error"])
        .values("action")
        .annotate(count=Count("id"))
        .order_by("-count", "action")[:limit]
    )

    response_data = {
        "filters": response_filters,
        "summary": summary,
        "interactions_by_day": interactions_by_day,
        "by_action": by_action,
        "by_category": by_category,
        "by_user": by_user,
        "failures_by_action": failures_by_action,
    }

    ai_insights = build_audit_ai_insights(
        filters=response_filters,
        summary=summary,
        interactions_by_day=interactions_by_day,
        by_action=by_action,
        by_category=by_category,
        by_user=by_user,
        failures_by_action=failures_by_action,
    )
    if ai_insights:
        response_data["ai_insights"] = ai_insights

    return JsonResponse({"data": response_data})
