from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from audit.models import AuditLog
from kawori.decorators import validate_user
from kawori.utils import format_date, paginate


@require_GET
@validate_user("admin")
def get_audit_logs(request, user):
    req = request.GET
    filters = {}

    if req.get("action"):
        filters["action"] = req.get("action")
    if req.get("category"):
        filters["category"] = req.get("category")
    if req.get("result"):
        filters["result"] = req.get("result")
    if req.get("user_id"):
        filters["user_id"] = req.get("user_id")
    if req.get("username"):
        filters["username__icontains"] = req.get("username")
    if req.get("ip_address"):
        filters["ip_address"] = req.get("ip_address")
    if req.get("date_from"):
        date_from = format_date(req.get("date_from"))
        if date_from:
            filters["created_at__gte"] = date_from
    if req.get("date_to"):
        date_to = format_date(req.get("date_to"))
        if date_to:
            filters["created_at__lte"] = date_to + timedelta(days=1)

    logs = AuditLog.objects.filter(**filters)
    page_size = req.get("page_size", 50)
    data = paginate(logs, req.get("page", 1), page_size)

    logs_data = [
        {
            "id": log.id,
            "action": log.action,
            "category": log.category,
            "result": log.result,
            "user_id": log.user_id,
            "username": log.username,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "path": log.path,
            "method": log.method,
            "target_model": log.target_model,
            "target_id": log.target_id,
            "detail": log.detail,
            "response_status": log.response_status,
            "created_at": log.created_at.isoformat(),
        }
        for log in data.get("data")
    ]

    data["page_size"] = page_size
    data["data"] = logs_data

    return JsonResponse({"data": data})


@require_GET
@validate_user("admin")
def get_audit_stats(request, user):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    by_category_24h = (
        AuditLog.objects.filter(created_at__gte=last_24h)
        .values("category")
        .annotate(count=Count("id"))
    )

    by_result_24h = (
        AuditLog.objects.filter(created_at__gte=last_24h)
        .values("result")
        .annotate(count=Count("id"))
    )

    by_category_7d = (
        AuditLog.objects.filter(created_at__gte=last_7d)
        .values("category")
        .annotate(count=Count("id"))
    )

    by_result_7d = (
        AuditLog.objects.filter(created_at__gte=last_7d)
        .values("result")
        .annotate(count=Count("id"))
    )

    failed_logins_24h = AuditLog.objects.filter(
        created_at__gte=last_24h,
        action="login",
        result="failure",
    ).count()

    return JsonResponse(
        {
            "data": {
                "last_24h": {
                    "by_category": list(by_category_24h),
                    "by_result": list(by_result_24h),
                },
                "last_7d": {
                    "by_category": list(by_category_7d),
                    "by_result": list(by_result_7d),
                },
                "failed_logins_24h": failed_logins_24h,
            }
        }
    )


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
        {"day": item["day"].isoformat() if item["day"] else None, "count": item["count"]} for item in interactions_by_day
    ]

    by_action = list(logs.values("action").annotate(count=Count("id")).order_by("-count", "action")[:limit])
    by_category = list(logs.values("category").annotate(count=Count("id")).order_by("-count", "category")[:limit])
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

    return JsonResponse(
        {
            "data": {
                "filters": response_filters,
                "summary": summary,
                "interactions_by_day": interactions_by_day,
                "by_action": by_action,
                "by_category": by_category,
                "by_user": by_user,
                "failures_by_action": failures_by_action,
            }
        }
    )
