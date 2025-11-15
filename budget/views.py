import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from budget.models import Budget
from kawori.decorators import validate_user


@require_GET
@validate_user("financial")
def get_all_budgets_view(request, user):

    budget_list = Budget.objects.filter(user=user)

    data = [
        {
            "id": budget.id,
            "name": budget.tag.name,
            "color": budget.tag.color,
            "allocation_percentage": float(budget.allocation_percentage),
        }
        for budget in budget_list
    ]
    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
def save_budget_view(request, user):
    data = json.loads(request.body)
    for item in data.get("data", []):
        budget = Budget.objects.filter(id=item.get("id"), user=user).first()
        if budget:
            budget.allocation_percentage = item.get("allocation_percentage", budget.allocation_percentage)
            budget.save()

    return JsonResponse({"msg": "Orçamento atualizado com sucesso"})
