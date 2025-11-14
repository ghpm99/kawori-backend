import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Sum, Count


from kawori.decorators import validate_user
from tag.models import Tag


@require_GET
@validate_user("financial")
def get_all_tag_view(request, user):
    req = request.GET
    filters = {}

    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")

    datas = (
        Tag.objects.filter(**filters, user=user)
        .annotate(
            total_payments=Count("invoices", distinct=True),
            total_value=Sum("invoices__value"),
            total_open=Sum("invoices__value_open"),
            total_closed=Sum("invoices__value_closed"),
            is_budget=Count("budgettag", distinct=True),
        )
        .order_by("name")
    )

    tags = [
        {
            "id": data.id,
            "name": data.name,
            "color": data.color,
            "total_payments": data.total_payments or 0,
            "total_value": data.total_value or 0,
            "total_open": data.total_open or 0,
            "total_closed": data.total_closed or 0,
            "is_budget": data.is_budget > 0,
        }
        for data in datas
    ]

    return JsonResponse({"data": tags})


@require_GET
@validate_user("financial")
def detail_tag_view(request, id, user):
    tag = Tag.objects.filter(id=id, user=user).first()

    if tag is None:
        return JsonResponse({"msg": "Tag não encontrada"}, status=404)

    tag = {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
    }

    return JsonResponse({"data": tag})


@require_POST
@validate_user("financial")
def include_new_tag_view(request, user):
    data = json.loads(request.body)

    tag_name = data.get("name")
    tag_color = data.get("color")

    tag_in_database = Tag.objects.filter(name=tag_name, user=user).first()

    if tag_in_database is not None:
        return JsonResponse({"msg": "Tag já existe"}, status=404)

    if not tag_name or tag_name.strip() == "":
        return JsonResponse({"msg": "Nome da tag é obrigatório"}, status=400)

    if tag_name.startswith("#"):
        return JsonResponse({"msg": "Nome da tag não pode iniciar com #"}, status=400)

    if not tag_color:
        return JsonResponse({"msg": "Cor da tag é obrigatória"}, status=400)

    Tag.objects.create(name=tag_name, color=tag_color, user=user)

    return JsonResponse({"msg": "Tag inclusa com sucesso"})


@require_POST
@validate_user("financial")
def save_tag_view(request, id, user):
    tag = Tag.objects.filter(id=id, user=user).first()

    if tag is None:
        return JsonResponse({"msg": "Tag não encontrada"}, status=404)

    data = json.loads(request.body)

    tag.name = data.get("name")
    tag.color = data.get("color")

    tag.save()

    return JsonResponse({"msg": "Tag atualizado com sucesso"})
