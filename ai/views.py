from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from ai.application.use_cases.metrics_breakdown import MetricsBreakdownUseCase
from ai.application.use_cases.metrics_overview import MetricsOverviewUseCase
from ai.application.use_cases.metrics_timeseries import MetricsTimeseriesUseCase
from ai.interfaces.api.serializers.metrics_breakdown_serializers import (
    MetricsBreakdownResponseSerializer,
)
from ai.interfaces.api.serializers.metrics_overview_serializers import (
    MetricsOverviewResponseSerializer,
)
from ai.interfaces.api.serializers.metrics_timeseries_serializers import (
    MetricsTimeseriesResponseSerializer,
)
from ai.models import AIExecutionEvent
from kawori.decorators import validate_user

DEFAULT_LOOKBACK_DAYS = 7


@require_GET
@validate_user("admin")
def metrics_overview(request, user):
    queryset, period = _build_filtered_queryset(request)
    payload, status_code = MetricsOverviewUseCase().execute(
        queryset=queryset,
        period=period,
        q_fn=_q,
        count_cls=Count,
        sum_cls=Sum,
        avg_cls=Avg,
        to_float_fn=_to_float,
        ratio_fn=_ratio,
    )
    serializer = MetricsOverviewResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def metrics_breakdown(request, user):
    queryset, period = _build_filtered_queryset(request)
    payload, status_code = MetricsBreakdownUseCase().execute(
        queryset=queryset,
        period=period,
        group_by=request.GET.get("group_by"),
        q_fn=_q,
        count_cls=Count,
        sum_cls=Sum,
        avg_cls=Avg,
        to_float_fn=_to_float,
        ratio_fn=_ratio,
    )
    serializer = MetricsBreakdownResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def metrics_timeseries(request, user):
    queryset, period = _build_filtered_queryset(request)
    payload, status_code = MetricsTimeseriesUseCase().execute(
        queryset=queryset,
        period=period,
        interval=request.GET.get("interval"),
        trunc_hour_fn=TruncHour,
        trunc_date_fn=TruncDate,
        count_cls=Count,
        q_fn=_q,
        sum_cls=Sum,
        avg_cls=Avg,
        ratio_fn=_ratio,
        to_float_fn=_to_float,
    )
    serializer = MetricsTimeseriesResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


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
