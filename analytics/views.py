from datetime import timedelta, datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from kawori.decorators import validate_user
from django.contrib.auth.models import User


# Create your views here.
@require_GET
@validate_user("financial")
def get_new_users(request, user):
    # Placeholder implementation
    date_joined = datetime.now() - timedelta(days=7)
    new_users_count = User.objects.filter(is_active=True, date_joined=date_joined).count()

    return JsonResponse({"new_users": new_users_count})
