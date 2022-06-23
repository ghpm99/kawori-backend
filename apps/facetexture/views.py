import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from kawori.decorators import add_cors_react_dev, validate_user
from facetexture.models import Facetexture, BDOClass


@add_cors_react_dev
@validate_user
@require_GET
def get_facetexture_config(request, user):

    facetexture = Facetexture.objects.filter(user=user).first()

    if facetexture is None:
        return JsonResponse({
            'characters': []
        })

    return JsonResponse(facetexture.characters, safe=False)


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_POST
def save_detail_view(request, user):

    data = json.loads(request.body)
    facetexture = Facetexture.objects.filter(user=user).first()

    if(facetexture is None):
        facetexture = Facetexture(
            user=user,
            characters=data
        )
        facetexture.save()
        return JsonResponse({'msg': 'Facetexture criado com sucesso'}, status=201)

    facetexture.characters = data
    facetexture.save()

    return JsonResponse({'msg': 'Facetexture atualizado com sucesso'})


@add_cors_react_dev
@validate_user
@require_GET
def get_bdo_class(request, user):

    def orderFunc(e):
        return e['name']

    bdo_classes = BDOClass.objects.all()

    bdo_class = [{
        'id': bdo_class.id,
        'name': bdo_class.name,
        'abbreviation': bdo_class.abbreviation,
    } for bdo_class in bdo_classes]

    bdo_class.sort(key=orderFunc)

    return JsonResponse({'class': bdo_class})
