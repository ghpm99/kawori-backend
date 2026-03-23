import json
from http import HTTPStatus

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from kawori.decorators import validate_user
from mailer.application.use_cases.email_preferences import EmailPreferencesUseCase
from mailer.interfaces.api.serializers.email_preferences_serializers import (
    UpdateEmailPreferencesSerializer,
)
from mailer.models import UserEmailPreference

ALLOWED_FIELDS = {"allow_all_emails", "allow_notification", "allow_promotional"}


@require_http_methods(["GET", "PUT"])
@validate_user("user")
def email_preferences(request, user):
    if request.method == "GET":
        payload, status_code = EmailPreferencesUseCase().execute_get(
            user=user,
            user_email_preference_model=UserEmailPreference,
        )
        return JsonResponse(payload, status=status_code)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"msg": "JSON inválido."}, status=HTTPStatus.BAD_REQUEST)

    serializer = UpdateEmailPreferencesSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=HTTPStatus.BAD_REQUEST,
        )

    payload, status_code = EmailPreferencesUseCase().execute_put(
        user=user,
        data=serializer.validated_data,
        user_email_preference_model=UserEmailPreference,
        allowed_fields=ALLOWED_FIELDS,
    )
    return JsonResponse(payload, status=status_code)
