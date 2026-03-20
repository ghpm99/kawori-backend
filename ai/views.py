from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from ai.models import AIExecutionEvent
from kawori.decorators import validate_user

DEFAULT_LOOKBACK_DAYS = 7


@require_GET
@validate_user("admin")
def metrics_overview(request, user):
    queryset, period = _build_filtered_queryset(request)
    summary = queryset.aggregate(
        total_calls=Count("id"),
        total_cost=Sum("cost_estimate"),
        success_calls=Count("id", filter=_q(success=True)),
        failed_calls=Count("id", filter=_q(success=False)),
        fallback_calls=Count("id", filter=_q(used_fallback=True)),
        retry_attempts=Sum("retry_count"),
        cache_hits=Count("id", filter=_q(cache_status="hit")),
        cache_misses=Count("id", filter=_q(cache_status="miss")),
        cache_bypass=Count("id", filter=_q(cache_status="bypass")),
        avg_latency_ms=Avg("latency_ms"),
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
    )

    total_calls = int(summary.get("total_calls") or 0)
    success_calls = int(summary.get("success_calls") or 0)
    fallback_calls = int(summary.get("fallback_calls") or 0)
    retry_attempts = int(summary.get("retry_attempts") or 0)
    cache_hits = int(summary.get("cache_hits") or 0)

    response = {
        "period": period,
        "totals": {
            "calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": int(summary.get("failed_calls") or 0),
            "cost_usd": _to_float(summary.get("total_cost")),
            "fallback_calls": fallback_calls,
            "retry_attempts": retry_attempts,
            "cache_hits": cache_hits,
            "cache_misses": int(summary.get("cache_misses") or 0),
            "cache_bypass": int(summary.get("cache_bypass") or 0),
            "avg_latency_ms": _to_float(summary.get("avg_latency_ms")),
            "prompt_tokens": int(summary.get("prompt_tokens") or 0),
            "completion_tokens": int(summary.get("completion_tokens") or 0),
            "total_tokens": int(summary.get("total_tokens") or 0),
        },
        "rates": {
            "success_rate": _ratio(success_calls, total_calls),
            "fallback_rate": _ratio(fallback_calls, total_calls),
            "retry_rate": _ratio(retry_attempts, total_calls),
            "cache_hit_rate": _ratio(cache_hits, total_calls),
        },
        "cardinality": {
            "features": queryset.values("feature_name")
            .exclude(feature_name="")
            .distinct()
            .count(),
            "providers": queryset.values("provider")
            .exclude(provider="")
            .distinct()
            .count(),
            "models": queryset.values("model").exclude(model="").distinct().count(),
            "task_types": queryset.values("task_type")
            .exclude(task_type="")
            .distinct()
            .count(),
        },
    }
    return JsonResponse({"data": response})


@require_GET
@validate_user("admin")
def metrics_breakdown(request, user):
    queryset, period = _build_filtered_queryset(request)
    group_by = str(request.GET.get("group_by") or "feature_name").strip()
    allowed_groups = {
        "feature_name",
        "provider",
        "model",
        "task_type",
        "cache_status",
        "success",
    }
    if group_by not in allowed_groups:
        return JsonResponse({"msg": "group_by inválido"}, status=400)

    rows = (
        queryset.values(group_by)
        .annotate(
            calls=Count("id"),
            success_calls=Count("id", filter=_q(success=True)),
            failed_calls=Count("id", filter=_q(success=False)),
            fallback_calls=Count("id", filter=_q(used_fallback=True)),
            retry_attempts=Sum("retry_count"),
            cost_usd=Sum("cost_estimate"),
            avg_latency_ms=Avg("latency_ms"),
            prompt_tokens=Sum("prompt_tokens"),
            completion_tokens=Sum("completion_tokens"),
            total_tokens=Sum("total_tokens"),
        )
        .order_by("-calls", group_by)
    )

    data = []
    for row in rows:
        calls = int(row.get("calls") or 0)
        success_calls = int(row.get("success_calls") or 0)
        data.append(
            {
                "group": row.get(group_by),
                "calls": calls,
                "success_calls": success_calls,
                "failed_calls": int(row.get("failed_calls") or 0),
                "success_rate": _ratio(success_calls, calls),
                "fallback_calls": int(row.get("fallback_calls") or 0),
                "retry_attempts": int(row.get("retry_attempts") or 0),
                "cost_usd": _to_float(row.get("cost_usd")),
                "avg_latency_ms": _to_float(row.get("avg_latency_ms")),
                "prompt_tokens": int(row.get("prompt_tokens") or 0),
                "completion_tokens": int(row.get("completion_tokens") or 0),
                "total_tokens": int(row.get("total_tokens") or 0),
            }
        )

    return JsonResponse(
        {
            "data": {
                "group_by": group_by,
                "period": period,
                "rows": data,
            }
        }
    )


@require_GET
@validate_user("admin")
def metrics_timeseries(request, user):
    queryset, period = _build_filtered_queryset(request)
    interval = str(request.GET.get("interval") or "day").strip().lower()
    if interval not in {"day", "hour"}:
        return JsonResponse({"msg": "interval inválido"}, status=400)

    bucket_fn = (
        TruncHour("created_at") if interval == "hour" else TruncDate("created_at")
    )
    rows = (
        queryset.annotate(bucket=bucket_fn)
        .values("bucket")
        .annotate(
            calls=Count("id"),
            success_calls=Count("id", filter=_q(success=True)),
            failed_calls=Count("id", filter=_q(success=False)),
            fallback_calls=Count("id", filter=_q(used_fallback=True)),
            retry_attempts=Sum("retry_count"),
            cost_usd=Sum("cost_estimate"),
            avg_latency_ms=Avg("latency_ms"),
            prompt_tokens=Sum("prompt_tokens"),
            completion_tokens=Sum("completion_tokens"),
            total_tokens=Sum("total_tokens"),
            cache_hits=Count("id", filter=_q(cache_status="hit")),
        )
        .order_by("bucket")
    )

    data = []
    for row in rows:
        calls = int(row.get("calls") or 0)
        success_calls = int(row.get("success_calls") or 0)
        bucket = row.get("bucket")
        data.append(
            {
                "bucket": bucket.isoformat() if bucket else None,
                "calls": calls,
                "success_calls": success_calls,
                "failed_calls": int(row.get("failed_calls") or 0),
                "success_rate": _ratio(success_calls, calls),
                "fallback_calls": int(row.get("fallback_calls") or 0),
                "retry_attempts": int(row.get("retry_attempts") or 0),
                "cache_hits": int(row.get("cache_hits") or 0),
                "cost_usd": _to_float(row.get("cost_usd")),
                "avg_latency_ms": _to_float(row.get("avg_latency_ms")),
                "prompt_tokens": int(row.get("prompt_tokens") or 0),
                "completion_tokens": int(row.get("completion_tokens") or 0),
                "total_tokens": int(row.get("total_tokens") or 0),
            }
        )

    return JsonResponse(
        {"data": {"interval": interval, "period": period, "rows": data}}
    )


@require_GET
@validate_user("admin")
def metrics_events(request, user):
    queryset, period = _build_filtered_queryset(request)

    page = _to_positive_int(request.GET.get("page"), default=1)
    page_size = _to_positive_int(request.GET.get("page_size"), default=50)
    page_size = min(page_size, 200)

    total = queryset.count()
    offset = (page - 1) * page_size
    events = queryset.order_by("-created_at")[offset : offset + page_size]

    data = [
        {
            "id": event.id,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "trace_id": event.trace_id,
            "feature_name": event.feature_name,
            "task_type": event.task_type,
            "provider": event.provider,
            "model": event.model,
            "success": event.success,
            "attempts": event.attempts,
            "retry_count": event.retry_count,
            "used_fallback": event.used_fallback,
            "latency_ms": event.latency_ms,
            "cache_status": event.cache_status,
            "prompt_tokens": event.prompt_tokens,
            "completion_tokens": event.completion_tokens,
            "total_tokens": event.total_tokens,
            "cost_estimate": _to_float(event.cost_estimate),
            "error_message": event.error_message,
            "metadata": event.metadata,
            "user_id": event.user_id,
        }
        for event in events
    ]

    return JsonResponse(
        {
            "data": {
                "period": period,
                "page": page,
                "page_size": page_size,
                "total": total,
                "rows": data,
            }
        }
    )


def _build_filtered_queryset(request):
    now = timezone.now()
    date_to = _parse_datetime(request.GET.get("date_to")) or now
    date_from = _parse_datetime(request.GET.get("date_from"))
    if date_from is None:
        date_from = date_to - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    queryset = AIExecutionEvent.objects.filter(
        created_at__gte=date_from, created_at__lte=date_to
    )

    feature_name = str(request.GET.get("feature_name") or "").strip()
    if feature_name:
        queryset = queryset.filter(feature_name=feature_name)

    provider = str(request.GET.get("provider") or "").strip()
    if provider:
        queryset = queryset.filter(provider=provider)

    model = str(request.GET.get("model") or "").strip()
    if model:
        queryset = queryset.filter(model=model)

    task_type = str(request.GET.get("task_type") or "").strip()
    if task_type:
        queryset = queryset.filter(task_type=task_type)

    cache_status = str(request.GET.get("cache_status") or "").strip()
    if cache_status:
        queryset = queryset.filter(cache_status=cache_status)

    success_filter = request.GET.get("success")
    if success_filter is not None:
        parsed_success = _to_bool(success_filter)
        if parsed_success is not None:
            queryset = queryset.filter(success=parsed_success)

    user_id = request.GET.get("user_id")
    if user_id:
        parsed_user_id = _to_positive_int(user_id, default=None)
        if parsed_user_id is not None:
            queryset = queryset.filter(user_id=parsed_user_id)

    period = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }
    return queryset, period


def _to_positive_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _to_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _to_bool(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_datetime(raw_value):
    if not raw_value:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    # accepts YYYY-MM-DD and ISO datetime
    try:
        if len(value) == 10:
            parsed = datetime.strptime(value, "%Y-%m-%d")
            return timezone.make_aware(parsed)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed
    except Exception:
        return None


def _q(**kwargs):
    from django.db.models import Q

    return Q(**kwargs)
