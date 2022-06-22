import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from kawori.decorators import add_cors_react_dev, validate_user
from facetexture.models import Facetexture


@add_cors_react_dev
@validate_user
@require_GET
def get_facetexture_config(request, user):

    facetexture = Facetexture.objects.filter(user=user).first()

    if facetexture is None:
        return JsonResponse({
            'characters': []
        })

    return JsonResponse(facetexture.characters)


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_POST
def save_detail_view(request, id, user):

    data = json.loads(request.body)
    payment = Facetexture.objects.filter(user=user).first()

    if(data is None):
        return JsonResponse({'msg': 'Facetexture not found'}, status=404)

    if data.get('type'):
        payment.type = data.get('type')
    if data.get('name'):
        payment.name = data.get('name')
    if data.get('payment_date'):
        payment.payment_date = data.get('payment_date')
    if data.get('fixed'):
        payment.fixed = data.get('fixed')
    if data.get('active'):
        payment.active = data.get('active')
    if data.get('value'):
        payment.value = data.get('value')

    payment.save()

    return JsonResponse({'msg': 'ok'})
