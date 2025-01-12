import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


from kawori.decorators import add_cors_react_dev, validate_super_user
from tag.models import Tag


@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_tag_view(request, user):
    req = request.GET
    filters = {}

    if req.get('name__icontains'):
        filters['name__icontains'] = req.get('name__icontains')

    datas = Tag.objects.filter(**filters, user=user).all().order_by('name')

    tags = [{
        'id': data.id,
        'name': data.name,
        'color': data.color
    } for data in datas]

    return JsonResponse({'data': tags})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def include_new_tag_view(request, user):
    data = json.loads(request.body)

    tag = Tag(
        name=data.get('name'),
        color=data.get('color'),
        user=user
    )

    tag.save()

    return JsonResponse({'msg': 'Tag inclusa com sucesso'})