from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from audit.ai_assist import build_audit_ai_insights
from audit.application.use_cases.get_audit_logs import GetAuditLogsUseCase
from audit.application.use_cases.get_audit_report import GetAuditReportUseCase
from audit.application.use_cases.get_audit_stats import GetAuditStatsUseCase
from audit.interfaces.api.serializers.audit_logs_serializers import (
    AuditLogsResponseSerializer,
)
from audit.interfaces.api.serializers.audit_report_serializers import (
    AuditReportResponseSerializer,
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
    payload, status_code = GetAuditReportUseCase().execute(
        request_get=request.GET,
        audit_log_model=AuditLog,
        format_date_fn=format_date,
        timedelta_cls=timedelta,
        trunc_date_cls=TruncDate,
        count_cls=Count,
        build_ai_insights_fn=build_audit_ai_insights,
    )
    serializer = AuditReportResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
