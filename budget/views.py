from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from kawori.decorators import validate_user


@require_GET
@validate_user("financial")
def get_all_budgets_view(request):
    return JsonResponse({"data": []})
