import io
import json
import os
from wsgiref.util import FileWrapper
from zipfile import ZipFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from kawori.decorators import add_cors_react_dev, validate_user
from facetexture.models import Facetexture, BDOClass, PreviewBackground
from PIL import Image


@add_cors_react_dev
@validate_user
@require_GET
def get_facetexture_config(request, user):

    facetexture = Facetexture.objects.filter(user=user).first()

    if facetexture is None:
        return JsonResponse({
            'characters': []
        })

    characters = facetexture.characters['characters']

    for character in characters:
        bdo_class = BDOClass.objects.filter(id=character['class']).first()
        character['class'] = {
            'id': bdo_class.id,
            'name': bdo_class.name,
            'abbreviation': bdo_class.abbreviation,
            'class_image': bdo_class.class_image.url
        }

    return JsonResponse(facetexture.characters, safe=False)


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_POST
def save_detail_view(request, user):

    data = json.loads(request.body)
    facetexture = Facetexture.objects.filter(user=user).first()

    if facetexture is None:
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

    req = request.GET
    filters = {}

    if req.get('id'):
        filters['id'] = req.get('id')

    bdo_classes = BDOClass.objects.filter(**filters).all()

    bdo_class = [{
        'id': bdo_class.id,
        'name': bdo_class.name,
        'abbreviation': bdo_class.abbreviation,
        'class_image': bdo_class.class_image.url if bdo_class.class_image else '',
    } for bdo_class in bdo_classes]

    bdo_class.sort(key=orderFunc)

    return JsonResponse({'class': bdo_class})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def preview_background(request, user):
    req_files = request.FILES
    if not req_files.get('background'):
        return JsonResponse({'msg': 'Nao existe nenhum background'}, status=400)

    facetexture = Facetexture.objects.filter(user=user).first()
    if not facetexture:
        return JsonResponse({'msg': 'Facetexture nao encontrado'}, status=404)

    backgroundModel = PreviewBackground.objects.first()
    if not backgroundModel:
        return JsonResponse({'msg': 'Fundo nao cadastrado'}, status=404)

    file = request.FILES.get('background').file
    image = Image.open(file)

    image = image.resize(size=(920, 837))

    width = 125
    height = 160

    countX = 0
    countY = 0

    characters = facetexture.characters['characters']

    background = Image.open(backgroundModel.image)

    for index, character in enumerate(characters):
        x = countX * (width + 5) + 11
        y = countY * (height + 5) + 11

        if (index % 7) == 6:
            countX = 0
            countY = countY + 1
        else:
            countX = countX + 1

        imageCrop = image.crop((x, y, x + width, y + height))

        background.paste(im=imageCrop, box=(x, y))

    response = HttpResponse(content_type="image/png")
    background.save(response, 'PNG')
    return response


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def download_background(request, user):
    req_files = request.FILES
    if not req_files.get('background'):
        return JsonResponse({'msg': 'Nao existe nenhum background'}, status=400)

    facetexture = Facetexture.objects.filter(user=user).first()
    if not facetexture:
        return JsonResponse({'msg': 'Facetexture nao encontrado'}, status=404)

    file = request.FILES.get('background').file
    image = Image.open(file)

    image = image.resize(size=(920, 837))

    width = 125
    height = 160

    countX = 0
    countY = 0

    characters = facetexture.characters['characters']

    backgrounds = []

    for index, character in enumerate(characters):
        x = countX * (width + 5) + 11
        y = countY * (height + 5) + 11

        if (index % 7) == 6:
            countX = 0
            countY = countY + 1
        else:
            countX = countX + 1

        imageCrop = image.crop((x, y, x + width, y + height))

        backgrounds.append({'name': '', 'image': imageCrop})

    for index, character in enumerate(characters):
        backgroundCharacter = backgrounds[index]
        backgroundCharacter['name'] = character['name']
        if character['show'] is False:
            continue
        bdoClass = BDOClass.objects.filter(id=character['class']).first()

        classImage = Image.open(bdoClass.image)
        classImage.thumbnail((50, 50), Image.ANTIALIAS)

        backgroundCharacter['image'].paste(classImage, (10, 10), classImage)

    with ZipFile('export.zip', 'w') as export_zip:
        for index, background in enumerate(backgrounds):
            file_object = io.BytesIO()
            background['image'].save(file_object, 'PNG')
            file_object.seek(0)

            export_zip.writestr(background['name'], file_object.getvalue())

    wrapper = FileWrapper(open('export.zip', 'rb'))
    content_type = 'application/zip'
    content_disposition = 'attachment; filename=export.zip'

    response = HttpResponse(wrapper, content_type=content_type)
    response['Content-Disposition'] = content_disposition
    os.remove('export.zip')
    return response
