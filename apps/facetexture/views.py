import io
import json
import os
import math
from django.db import connection
from wsgiref.util import FileWrapper
from zipfile import ZipFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from kawori.decorators import add_cors_react_dev, validate_user
from facetexture.models import Facetexture, BDOClass, PreviewBackground, Character
from PIL import Image, ImageOps


@add_cors_react_dev
@validate_user
@require_GET
def get_facetexture_config(request, user):

    characters = Character.objects.filter(user=user, active=True).all().order_by('order')

    data = []

    for character in characters:
        character_data = {
            'id': character.id,
            'name': character.name,
            'show': character.show,
            'image': character.image,
            'order': character.order,
            'upload': character.upload,
            'class': {
                'id': character.bdoClass.id,
                'name': character.bdoClass.name,
                'abbreviation': character.bdoClass.abbreviation,
                'class_image': character.bdoClass.class_image.url
            }
        }

        data.append(character_data)

    return JsonResponse({'characters': data})


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

    characters = Character.objects.filter(user=user, active=True).order_by('order').all()
    if not characters:
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

    height_background = math.ceil(characters.__len__() / 7)

    background = Image.new(mode="RGB", size=(930, height_background*170))

    for index, character in enumerate(characters):
        x = countX * (width + 5) + 11
        y = countY * (height + 5) + 11

        if (index % 7) == 6:
            countX = 0
            countY = countY + 1
        else:
            countX = countX + 1

        imageCrop = image.crop((x, y, x + width, y + height))

        if character.show is True:
            classImage = Image.open(character.bdoClass.image)
            classImage.thumbnail((50, 50), Image.ANTIALIAS)

            imageCrop.paste(classImage, (10, 10), classImage)

        if character.name.__len__() < 20:
            imageCrop = ImageOps.expand(imageCrop, border=(3, 3, 3, 3), fill='red')
            background.paste(im=imageCrop, box=(x-3, y-3))
        else:
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

    characters = Character.objects.filter(user=user, active=True).order_by('order').all()
    if not characters:
        return JsonResponse({'msg': 'Facetexture nao encontrado'}, status=404)

    file = request.FILES.get('background').file
    image = Image.open(file)

    image = image.resize(size=(920, 837))

    width = 125
    height = 160

    countX = 0
    countY = 0

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

        if character.show is True:
            classImage = Image.open(character.bdoClass.image)
            classImage.thumbnail((50, 50), Image.ANTIALIAS)

            imageCrop.paste(classImage, (10, 10), classImage)

        backgrounds.append({'name': character.name, 'image': imageCrop})

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


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def reorder_character(request, user, id):

    data = json.loads(request.body)
    index_destination = data.get('index_destination')

    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse({'data': 'Não foi encontrado personagem com esse ID'})

    query = """
        UPDATE
            facetexture_character
        SET
            "order" = %(order)s
        WHERE
            1 = 1
            AND id = %(id)s
    """

    with connection.cursor() as cursor:
        cursor.execute(query, {
            'order': index_destination,
            'id': id
        })

    query = """
        UPDATE
            facetexture_character
        SET
            "order" = (
                CASE
                    WHEN %(new_order)s > %(current_order)s THEN ("order" - 1)
                    WHEN %(new_order)s < %(current_order)s THEN ("order" + 1)
                END
            )
        WHERE
            1 = 1
            AND CASE
                WHEN %(new_order)s > %(current_order)s THEN (
                    "order" <= %(new_order)s
                    AND "order" > %(current_order)s
                )
                WHEN %(new_order)s < %(current_order)s THEN (
                    "order" >= %(new_order)s
                    AND "order" < %(current_order)s
                )
            END
            AND id <> %(id)s
            AND active = true
    """

    with connection.cursor() as cursor:
        cursor.execute(query, {
            'current_order': character.order,
            'new_order': index_destination,
            'id': id
        })

    characters = Character.objects.filter(user=user, active=True).all().order_by('order')

    data = []

    for character in characters:
        character_data = {
            'id': character.id,
            'order': character.order
        }

        data.append(character_data)

    return JsonResponse({'data': data})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def change_class_character(request, user, id):

    data = json.loads(request.body)
    new_class = data.get('new_class')

    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse({'data': 'Não foi encontrado personagem com esse ID'})

    bdo_class = BDOClass.objects.filter(id=new_class).first()

    if bdo_class is None:
        return JsonResponse({'data': 'Não foi encontrado classe'})

    character.bdoClass = bdo_class
    character.save()

    return JsonResponse({
        'class': {
            'id': bdo_class.id,
            'name': bdo_class.name,
            'abbreviation': bdo_class.abbreviation,
            'class_image': bdo_class.class_image.url
        }
    })


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def change_character_name(request, user, id):

    data = json.loads(request.body)
    new_name = data.get('name')

    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse({'data': 'Não foi encontrado personagem com esse ID'})

    character.name = new_name
    character.save()

    return JsonResponse({'data': 'Nome atualizado com sucesso'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def new_character(request, user):
    bdo_class = BDOClass.objects.first()

    last_order = Character.objects.filter(user=user, active=True).latest('order').order + 1

    character = Character(
        name='default{}'.format(last_order),
        show=True,
        image=bdo_class.class_image.url,
        order=last_order,
        upload=False,
        bdoClass=bdo_class,
        user=user,
    )
    character.save()

    character_data = {
        'id': character.id,
        'name': character.name,
        'show': character.show,
        'image': character.image,
        'order': character.order,
        'upload': character.upload,
        'class': {
            'id': character.bdoClass.id,
            'name': character.bdoClass.name,
            'abbreviation': character.bdoClass.abbreviation,
            'class_image': character.bdoClass.class_image.url
        }
    }

    return JsonResponse({
        'character': character_data
    })


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def change_show_class_icon(request, user, id):

    data = json.loads(request.body)
    new_value = data.get('show')

    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse({'data': 'Não foi encontrado personagem com esse ID'})

    character.show = new_value
    character.save()

    return JsonResponse({'data': 'Visibilidade atualizado com sucesso'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def delete_character(request, user, id):
    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse({'data': 'Não foi encontrado personagem com esse ID'})

    character.active = False
    character.save()

    return JsonResponse({'data': 'Personagem deletado com sucesso'})
