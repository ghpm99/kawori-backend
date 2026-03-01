import json
from functools import wraps

from django.contrib.auth.models import User

from audit.models import (
    CATEGORY_AUTH,
    RESULT_ERROR,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    AuditLog,
)
from authentication.utils import get_client_ip


SENSITIVE_FIELDS = {"password", "new_password", "token", "access_token", "refresh_token", "secret"}


def sanitize_body(body, max_size=2048):
    if not body:
        return {}
    try:
        if isinstance(body, (bytes, memoryview)):
            body = body[:max_size].decode("utf-8", errors="replace")
        elif isinstance(body, str):
            body = body[:max_size]
        data = json.loads(body)
        if isinstance(data, dict):
            return {k: "***" if k in SENSITIVE_FIELDS else v for k, v in data.items()}
        return data
    except (json.JSONDecodeError, ValueError):
        return {}


def audit_log(action, category, target_model=""):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = kwargs.get("user")
            ip_address = get_client_ip(request) or None
            target_id = str(kwargs.get("id", ""))
            detail = sanitize_body(request.body)

            try:
                response = view_func(request, *args, **kwargs)
                status_code = response.status_code
                result = RESULT_SUCCESS if status_code < 400 else RESULT_FAILURE

                AuditLog.objects.create(
                    action=action,
                    category=category,
                    result=result,
                    user=user,
                    username=user.username if user else "",
                    ip_address=ip_address,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    path=request.path,
                    method=request.method,
                    target_model=target_model,
                    target_id=target_id,
                    detail=detail,
                    response_status=status_code,
                )

                return response
            except Exception:
                AuditLog.objects.create(
                    action=action,
                    category=category,
                    result=RESULT_ERROR,
                    user=user,
                    username=user.username if user else "",
                    ip_address=ip_address,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    path=request.path,
                    method=request.method,
                    target_model=target_model,
                    target_id=target_id,
                    detail=detail,
                    response_status=None,
                )
                raise

        return _wrapped_view

    return decorator


def audit_log_auth(action):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            ip_address = get_client_ip(request) or None
            detail = sanitize_body(request.body)

            user = None
            username = ""
            if isinstance(detail, dict):
                username = detail.get("username", "")
                email = detail.get("email", "")
                if username:
                    user = User.objects.filter(username=username).first()
                elif email:
                    user = User.objects.filter(email__iexact=email).first()
                if user:
                    username = user.username

            try:
                response = view_func(request, *args, **kwargs)
                status_code = response.status_code
                result = RESULT_SUCCESS if status_code < 400 else RESULT_FAILURE

                AuditLog.objects.create(
                    action=action,
                    category=CATEGORY_AUTH,
                    result=result,
                    user=user,
                    username=username,
                    ip_address=ip_address,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    path=request.path,
                    method=request.method,
                    detail=detail,
                    response_status=status_code,
                )

                return response
            except Exception:
                AuditLog.objects.create(
                    action=action,
                    category=CATEGORY_AUTH,
                    result=RESULT_ERROR,
                    user=user,
                    username=username,
                    ip_address=ip_address,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    path=request.path,
                    method=request.method,
                    detail=detail,
                    response_status=None,
                )
                raise

        return _wrapped_view

    return decorator
