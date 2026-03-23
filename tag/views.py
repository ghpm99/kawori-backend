import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from kawori.decorators import validate_user
from tag.application.use_cases.get_all_tags import GetAllTagsUseCase
from tag.application.use_cases.get_tag_detail import GetTagDetailUseCase
from tag.interfaces.api.serializers.tag_serializers import TagListQuerySerializer
from tag.models import Tag


@require_GET
@validate_user("financial")
def get_all_tag_view(request, user):
    serializer = TagListQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)

    tags = GetAllTagsUseCase().execute(
        user=user,
        name_icontains=serializer.validated_data.get("name__icontains"),
    )
    return JsonResponse({"data": tags})


@require_GET
@validate_user("financial")
def detail_tag_view(request, id, user):
    tag = GetTagDetailUseCase().execute(user=user, tag_model=Tag, tag_id=id)
    if tag is None:
        return JsonResponse({"msg": "Tag não encontrada"}, status=404)

    return JsonResponse({"data": tag})


@require_POST
@validate_user("financial")
@audit_log("tag.create", CATEGORY_FINANCIAL, "Tag")
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
@audit_log("tag.update", CATEGORY_FINANCIAL, "Tag")
def save_tag_view(request, id, user):
    tag = Tag.objects.filter(id=id, user=user).first()

    if tag is None:
        return JsonResponse({"msg": "Tag não encontrada"}, status=404)

    data = json.loads(request.body)

    tag.name = data.get("name")
    tag.color = data.get("color")

    tag.save()

    return JsonResponse({"msg": "Tag atualizado com sucesso"})
