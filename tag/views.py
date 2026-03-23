import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from kawori.decorators import validate_user
from tag.application.use_cases.create_tag import CreateTagUseCase
from tag.application.use_cases.get_all_tags import GetAllTagsUseCase
from tag.application.use_cases.get_tag_detail import GetTagDetailUseCase
from tag.application.use_cases.save_tag import SaveTagUseCase
from tag.interfaces.api.serializers.tag_serializers import (
    TagCreatePayloadSerializer,
    TagListQuerySerializer,
)
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

    payload, status_code = CreateTagUseCase().validate_uniqueness(
        user=user,
        tag_model=Tag,
        name=tag_name,
    )
    if status_code is not None:
        return JsonResponse(payload, status=status_code)

    serializer = TagCreatePayloadSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    payload, status_code = CreateTagUseCase().create(
        user=user,
        tag_model=Tag,
        name=tag_name,
        color=tag_color,
    )

    return JsonResponse(payload, status=status_code)


@require_POST
@validate_user("financial")
@audit_log("tag.update", CATEGORY_FINANCIAL, "Tag")
def save_tag_view(request, id, user):
    data = json.loads(request.body)

    _, payload, status_code = SaveTagUseCase().execute(
        user=user,
        tag_model=Tag,
        tag_id=id,
        payload=data,
    )
    return JsonResponse(payload, status=status_code)
