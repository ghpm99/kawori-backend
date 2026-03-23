import io
import json
import math
import os
from wsgiref.util import FileWrapper
from zipfile import ZipFile

from django.conf import settings
from django.db import connection, transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, ImageOps

from audit.decorators import audit_log
from audit.models import CATEGORY_FACETEXTURE
from facetexture.application.use_cases.get_bdo_class import GetBDOClassUseCase
from facetexture.application.use_cases.get_facetexture_config import (
    GetFacetextureConfigUseCase,
)
from facetexture.application.use_cases.get_image_class import GetImageClassUseCase
from facetexture.application.use_cases.get_symbol_class import GetSymbolClassUseCase
from facetexture.application.use_cases.save_detail import SaveDetailUseCase
from facetexture.application.use_cases.change_show_class_icon import (
    ChangeShowClassIconUseCase,
)
from facetexture.application.use_cases.change_character_name import (
    ChangeCharacterNameUseCase,
)
from facetexture.application.use_cases.change_class_character import (
    ChangeClassCharacterUseCase,
)
from facetexture.interfaces.api.serializers.facetexture_serializers import (
    ClassAssetErrorResponseSerializer,
    ClassAssetPathSerializer,
    ChangeClassCharacterRequestSerializer,
    ChangeClassCharacterResponseSerializer,
    ChangeCharacterNameRequestSerializer,
    ChangeCharacterNameResponseSerializer,
    ChangeShowClassIconRequestSerializer,
    ChangeShowClassIconResponseSerializer,
    GetBDOClassQuerySerializer,
    GetBDOClassResponseSerializer,
    GetFacetextureConfigResponseSerializer,
    SaveDetailRequestSerializer,
    SaveDetailResponseSerializer,
)
from facetexture.models import BDOClass, Character, Facetexture
from kawori.decorators import validate_user
from kawori.utils import get_image_class, get_symbol_class


def get_bdo_class_image_url(class_id):
    return settings.BASE_URL + reverse("facetexture_get_image_class", args=[class_id])


def get_bdo_class_symbol_url(class_id):
    return settings.BASE_URL + reverse("facetexture_get_symbol_class", args=[class_id])


def verify_valid_symbol(symbol: str) -> bool:
    valid_symbols = ["P", "G", "D"]
    return symbol in valid_symbols


@require_GET
@validate_user("blackdesert")
def get_facetexture_config(request, user):
    payload = GetFacetextureConfigUseCase().execute(
        user=user,
        character_model=Character,
        class_image_url_fn=get_bdo_class_image_url,
    )
    serializer = GetFacetextureConfigResponseSerializer(payload)
    return JsonResponse(serializer.data)


@require_POST
@validate_user("blackdesert")
@audit_log("facetexture.save", CATEGORY_FACETEXTURE, "Facetexture")
def save_detail_view(request, user):
    data = json.loads(request.body)
    request_serializer = SaveDetailRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = SaveDetailUseCase().execute(
        user=user,
        data=request_serializer.validated_data,
        facetexture_model=Facetexture,
    )
    response_serializer = SaveDetailResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


@require_GET
@validate_user("blackdesert")
def get_bdo_class(request, user):
    query_serializer = GetBDOClassQuerySerializer(data=request.GET)
    query_serializer.is_valid(raise_exception=True)

    payload = GetBDOClassUseCase().execute(
        validated_data=query_serializer.validated_data,
        bdo_class_model=BDOClass,
        class_image_url_fn=get_bdo_class_image_url,
    )
    response_serializer = GetBDOClassResponseSerializer(payload)
    return JsonResponse(response_serializer.data)


@require_POST
@validate_user("blackdesert")
@audit_log("facetexture.preview", CATEGORY_FACETEXTURE, "Facetexture")
def preview_background(request, user):
    req_files = request.FILES
    if not req_files.get("background"):
        return JsonResponse({"msg": "Nao existe nenhum background"}, status=400)

    characters = (
        Character.objects.filter(user=user, active=True).order_by("order").all()
    )
    if not characters:
        return JsonResponse({"msg": "Facetexture nao encontrado"}, status=400)

    file = request.FILES.get("background").file
    image = Image.open(file)

    icon_style = request.POST.get("icon_style", "P")
    if not verify_valid_symbol(icon_style):
        return JsonResponse({"msg": "Estilo de simbolo invalido"}, status=400)

    image = image.resize(size=(920, 1157))

    width = 125
    height = 160

    countX = 0
    countY = 0

    height_background = math.ceil(characters.__len__() / 7)

    background = Image.new(mode="RGB", size=(930, height_background * 170))

    for index, character in enumerate(characters):
        x = countX * (width + 5) + 11
        y = countY * (height + 5) + 11

        if (index % 7) == 6:
            countX = 0
            countY = countY + 1
        else:
            countX = countX + 1

        imageCrop = image.crop((x, y, x + width, y + height)).convert("RGBA")

        if character.show is True:
            classImage = get_symbol_class(
                character.bdoClass, symbol_style=icon_style
            ).convert("RGBA")

            imageCrop.paste(classImage, (10, 10), classImage)

        if character.name.__len__() < 20:
            imageCrop = ImageOps.expand(imageCrop, border=(3, 3, 3, 3), fill="red")
            background.paste(im=imageCrop, box=(x - 3, y - 3))
        else:
            background.paste(im=imageCrop, box=(x, y))

    response = HttpResponse(content_type="image/png")
    background.save(response, "PNG")
    return response


@require_POST
@validate_user("blackdesert")
@audit_log("facetexture.download", CATEGORY_FACETEXTURE, "Facetexture")
def download_background(request, user):
    req_files = request.FILES
    if not req_files.get("background"):
        return JsonResponse({"msg": "Nao existe nenhum background"}, status=400)

    characters = (
        Character.objects.filter(user=user, active=True).order_by("order").all()
    )
    if not characters:
        return JsonResponse({"msg": "Facetexture nao encontrado"}, status=404)

    file = request.FILES.get("background").file
    image = Image.open(file)
    icon_style = request.POST.get("icon_style", "P")
    if not verify_valid_symbol(icon_style):
        return JsonResponse({"msg": "Estilo de simbolo invalido"}, status=400)

    image = image.resize(size=(920, 1157))

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

        imageCrop = image.crop((x, y, x + width, y + height)).convert("RGBA")

        if character.show is True:
            classImage = get_symbol_class(
                character.bdoClass, symbol_style=icon_style
            ).convert("RGBA")

            imageCrop.paste(classImage, (10, 10), classImage)

        backgrounds.append({"name": character.name, "image": imageCrop})

    with ZipFile("export.zip", "w") as export_zip:
        for index, background in enumerate(backgrounds):
            file_object = io.BytesIO()
            background["image"].save(file_object, "PNG")
            file_object.seek(0)

            export_zip.writestr(background["name"], file_object.getvalue())

    wrapper = FileWrapper(open("export.zip", "rb"))
    content_type = "application/zip"
    content_disposition = "attachment; filename=export.zip"

    response = HttpResponse(wrapper, content_type=content_type)
    response["Content-Disposition"] = content_disposition
    os.remove("export.zip")
    return response


@require_POST
@validate_user("blackdesert")
@audit_log("character.reorder", CATEGORY_FACETEXTURE, "Character")
def reorder_character(request, user, id):
    data = json.loads(request.body)
    index_destination = data.get("index_destination")

    if index_destination is None:
        return JsonResponse({"data": "Index de destino não informado"}, status=400)

    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse(
            {"data": "Não foi encontrado personagem com esse ID"}, status=404
        )

    with transaction.atomic():
        query = """
            UPDATE
                facetexture_character
            SET
                "order" = %(order)s
            WHERE
                1 = 1
                AND id = %(id)s
                AND user_id = %(user)s
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query, {"order": index_destination, "id": id, "user": user.id}
            )

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
                AND user_id = %(user)s
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "current_order": character.order,
                    "new_order": index_destination,
                    "id": id,
                    "user": user.id,
                },
            )

    characters = (
        Character.objects.filter(user=user, active=True).all().order_by("order")
    )

    data = []

    for character in characters:
        character_data = {"id": character.id, "order": character.order}

        data.append(character_data)

    return JsonResponse({"data": data})


@require_POST
@validate_user("blackdesert")
@audit_log("character.change_class", CATEGORY_FACETEXTURE, "Character")
def change_class_character(request, user, id):
    data = json.loads(request.body)
    request_serializer = ChangeClassCharacterRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = ChangeClassCharacterUseCase().execute(
        user=user,
        character_id=id,
        data=request_serializer.validated_data,
        character_model=Character,
        bdo_class_model=BDOClass,
        class_image_fn=get_bdo_class_image_url,
    )
    response_serializer = ChangeClassCharacterResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


@require_POST
@validate_user("blackdesert")
@audit_log("character.change_name", CATEGORY_FACETEXTURE, "Character")
def change_character_name(request, user, id):
    data = json.loads(request.body)
    request_serializer = ChangeCharacterNameRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = ChangeCharacterNameUseCase().execute(
        user=user,
        character_id=id,
        data=request_serializer.validated_data,
        character_model=Character,
    )
    response_serializer = ChangeCharacterNameResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


@require_POST
@validate_user("blackdesert")
@audit_log("character.create", CATEGORY_FACETEXTURE, "Character")
def new_character(request, user):
    MAXIMUM_FACETEXTURE_CHARACTERS = 44
    character_count = Character.objects.filter(user=user, active=True).count()

    if character_count >= MAXIMUM_FACETEXTURE_CHARACTERS:
        return JsonResponse(
            {"data": f"O limite de facetexture são {MAXIMUM_FACETEXTURE_CHARACTERS}!"},
            status=400,
        )

    data = json.loads(request.body)
    name = data.get("name", "")
    visible_class = data.get("visible")
    class_id = data.get("classId")

    bdo_class = BDOClass.objects.filter(id=class_id).first()
    if bdo_class is None:
        return JsonResponse({"data": "Classe não encontrada"}, status=400)

    if character_count == 0:
        new_order = 0
    else:
        last_order = Character.objects.filter(user=user, active=True).latest("order")
        new_order = last_order.order + 1

    image_url = get_bdo_class_image_url(bdo_class.id)

    character = Character(
        name=name,
        show=visible_class,
        image=image_url,
        order=new_order,
        upload=False,
        bdoClass=bdo_class,
        user=user,
    )
    character.save()

    character_data = {
        "id": character.id,
        "name": character.name,
        "show": character.show,
        "image": character.image,
        "order": character.order,
        "upload": character.upload,
        "class": {
            "id": character.bdoClass.id,
            "name": character.bdoClass.name,
            "abbreviation": character.bdoClass.abbreviation,
            "class_image": image_url,
        },
    }

    return JsonResponse({"character": character_data})


@require_POST
@validate_user("blackdesert")
@audit_log("character.toggle_icon", CATEGORY_FACETEXTURE, "Character")
def change_show_class_icon(request, user, id):
    data = json.loads(request.body)
    request_serializer = ChangeShowClassIconRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = ChangeShowClassIconUseCase().execute(
        user=user,
        character_id=id,
        data=request_serializer.validated_data,
        character_model=Character,
    )
    response_serializer = ChangeShowClassIconResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


@require_POST
@validate_user("blackdesert")
@audit_log("character.delete", CATEGORY_FACETEXTURE, "Character")
def delete_character(request, user, id):
    character = Character.objects.filter(id=id, user=user).first()

    if character is None:
        return JsonResponse(
            {"data": "Não foi encontrado personagem com esse ID"}, status=404
        )

    character.active = False
    character.save()

    return JsonResponse({"data": "Personagem deletado com sucesso"})


@require_GET
def get_symbol_class_view(request, id):
    path_serializer = ClassAssetPathSerializer(data={"id": id})
    path_serializer.is_valid(raise_exception=True)

    payload, status_code, image_buffer = GetSymbolClassUseCase().execute(
        class_id=path_serializer.validated_data["id"],
        bdo_class_model=BDOClass,
        get_symbol_class_fn=get_symbol_class,
        io_module=io,
    )
    if payload is not None:
        serializer = ClassAssetErrorResponseSerializer(payload)
        return JsonResponse(serializer.data, status=status_code)

    return FileResponse(image_buffer, content_type="image/png")


@require_GET
def get_image_class_view(request, id):
    path_serializer = ClassAssetPathSerializer(data={"id": id})
    path_serializer.is_valid(raise_exception=True)

    payload, status_code, image_buffer = GetImageClassUseCase().execute(
        class_id=path_serializer.validated_data["id"],
        bdo_class_model=BDOClass,
        get_image_class_fn=get_image_class,
        io_module=io,
    )
    if payload is not None:
        serializer = ClassAssetErrorResponseSerializer(payload)
        return JsonResponse(serializer.data, status=status_code)

    return FileResponse(image_buffer, content_type="image/png")
