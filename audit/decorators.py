import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.models import User
from django.http import RawPostDataException
from rest_framework_simplejwt.tokens import AccessToken

from audit.models import (
    CATEGORY_AUTH,
    RESULT_ERROR,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    AuditLog,
)
from authentication.utils import get_client_ip

SENSITIVE_FIELDS = {
    "password",
    "new_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
}


def _sanitize_value(key, value):
    if isinstance(key, str) and key.lower() in SENSITIVE_FIELDS:
        return "***"

    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_value("", item) for item in value]

    return value


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
            return {k: _sanitize_value(k, v) for k, v in data.items()}
        if isinstance(data, list):
            return [_sanitize_value("", item) for item in data]
        return data
    except (json.JSONDecodeError, ValueError):
        return {}


def sanitize_query_params(request):
    if not request.GET:
        return {}

    query = {}
    for key in request.GET.keys():
        values = request.GET.getlist(key)
        value = values[0] if len(values) == 1 else values
        query[key] = _sanitize_value(key, value)

    return query


def sanitize_request_detail(request):
    content_type = (request.META.get("CONTENT_TYPE") or "").lower()

    if content_type.startswith("multipart/form-data"):
        detail = {}
        for key in request.POST.keys():
            values = request.POST.getlist(key)
            value = values[0] if len(values) == 1 else values
            detail[key] = _sanitize_value(key, value)
    else:
        try:
            detail = sanitize_body(request.body)
        except RawPostDataException:
            detail = {}

    query_params = sanitize_query_params(request)

    if query_params:
        if isinstance(detail, dict):
            detail["query_params"] = query_params
        else:
            detail = {"body": detail, "query_params": query_params}

    return detail


def _create_audit_log_safe(**kwargs):
    try:
        AuditLog.objects.create(**kwargs)
    except Exception:
        return None


def get_user_from_access_token(request):
    access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)
    if not access_token_cookie:
        return None

    try:
        access_token = AccessToken(access_token_cookie)
        access_token.verify()
        access_token.verify_token_type()
        user_id = access_token.get("user_id")
        if not user_id:
            return None
        return User.objects.filter(id=user_id).first()
    except Exception:
        return None


def audit_log(action, category, target_model=""):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = kwargs.get("user")
            ip_address = get_client_ip(request) or None
            target_id = str(kwargs.get("id", ""))
            detail = sanitize_request_detail(request)

            try:
                response = view_func(request, *args, **kwargs)
                status_code = response.status_code
                result = RESULT_SUCCESS if status_code < 400 else RESULT_FAILURE

                _create_audit_log_safe(
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
                _create_audit_log_safe(
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
            detail = sanitize_request_detail(request)

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

                if not user:
                    user = get_user_from_access_token(request)
                    if user:
                        username = user.username

            try:
                response = view_func(request, *args, **kwargs)
                status_code = response.status_code
                result = RESULT_SUCCESS if status_code < 400 else RESULT_FAILURE

                _create_audit_log_safe(
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
                _create_audit_log_safe(
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
