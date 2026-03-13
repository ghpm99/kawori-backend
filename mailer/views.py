import json
from http import HTTPStatus

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from kawori.decorators import validate_user
from mailer.models import UserEmailPreference


ALLOWED_FIELDS = {"allow_all_emails", "allow_notification", "allow_promotional"}


@require_http_methods(["GET", "PUT"])
@validate_user("user")
def email_preferences(request, user):
    pref, _ = UserEmailPreference.objects.get_or_create(user=user)

    if request.method == "GET":
        return JsonResponse({
            "allow_all_emails": pref.allow_all_emails,
            "allow_notification": pref.allow_notification,
            "allow_promotional": pref.allow_promotional,
        })

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"msg": "JSON inválido."}, status=HTTPStatus.BAD_REQUEST)

    changed_fields = []
    for field in ALLOWED_FIELDS:
        if field in data:
            value = data[field]
            if not isinstance(value, bool):
                return JsonResponse(
                    {"msg": f"Campo '{field}' deve ser booleano."}, status=HTTPStatus.BAD_REQUEST
                )
            setattr(pref, field, value)
            changed_fields.append(field)

    if changed_fields:
        pref.save(update_fields=changed_fields + ["updated_at"])

    return JsonResponse({
        "allow_all_emails": pref.allow_all_emails,
        "allow_notification": pref.allow_notification,
        "allow_promotional": pref.allow_promotional,
    })
