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
from facetexture.application.use_cases.delete_character import DeleteCharacterUseCase
from facetexture.application.use_cases.reorder_character import ReorderCharacterUseCase
from facetexture.application.use_cases.new_character import NewCharacterUseCase
from facetexture.application.use_cases.preview_background import PreviewBackgroundUseCase
from facetexture.application.use_cases.download_background import (
    DownloadBackgroundUseCase,
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
    DeleteCharacterResponseSerializer,
    DownloadBackgroundRequestSerializer,
    DownloadBackgroundResponseSerializer,
    GetBDOClassQuerySerializer,
    GetBDOClassResponseSerializer,
    GetFacetextureConfigResponseSerializer,
    NewCharacterRequestSerializer,
    NewCharacterResponseSerializer,
    PreviewBackgroundRequestSerializer,
    PreviewBackgroundResponseSerializer,
    ReorderCharacterRequestSerializer,
    ReorderCharacterResponseSerializer,
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
    request_serializer = PreviewBackgroundRequestSerializer(data=request.POST)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code, background = PreviewBackgroundUseCase().execute(
        user=user,
        request_files=request.FILES,
        request_post=request_serializer.validated_data,
        character_model=Character,
        image_module=Image,
        image_ops_module=ImageOps,
        get_symbol_class_fn=get_symbol_class,
        verify_valid_symbol_fn=verify_valid_symbol,
        math_module=math,
    )
    if payload is not None:
        response_serializer = PreviewBackgroundResponseSerializer(payload)
        return JsonResponse(response_serializer.data, status=status_code)

    response = HttpResponse(content_type="image/png")
    background.save(response, "PNG")
    return response


@require_POST
@validate_user("blackdesert")
@audit_log("facetexture.download", CATEGORY_FACETEXTURE, "Facetexture")
def download_background(request, user):
    request_serializer = DownloadBackgroundRequestSerializer(data=request.POST)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code, export_path = DownloadBackgroundUseCase().execute(
        user=user,
        request_files=request.FILES,
        request_post=request_serializer.validated_data,
        character_model=Character,
        image_module=Image,
        get_symbol_class_fn=get_symbol_class,
        verify_valid_symbol_fn=verify_valid_symbol,
        io_module=io,
        zipfile_class=ZipFile,
    )
    if payload is not None:
        response_serializer = DownloadBackgroundResponseSerializer(payload)
        return JsonResponse(response_serializer.data, status=status_code)

    wrapper = FileWrapper(open(export_path, "rb"))
    content_type = "application/zip"
    content_disposition = "attachment; filename=export.zip"

    response = HttpResponse(wrapper, content_type=content_type)
    response["Content-Disposition"] = content_disposition
    os.remove(export_path)
    return response


@require_POST
@validate_user("blackdesert")
@audit_log("character.reorder", CATEGORY_FACETEXTURE, "Character")
def reorder_character(request, user, id):
    data = json.loads(request.body)
    request_serializer = ReorderCharacterRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = ReorderCharacterUseCase().execute(
        user=user,
        character_id=id,
        data=request_serializer.validated_data,
        character_model=Character,
        transaction_module=transaction,
        connection_module=connection,
    )
    response_serializer = ReorderCharacterResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


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
    data = json.loads(request.body)
    request_serializer = NewCharacterRequestSerializer(data=data)
    request_serializer.is_valid(raise_exception=True)

    payload, status_code = NewCharacterUseCase().execute(
        user=user,
        data=request_serializer.validated_data,
        character_model=Character,
        bdo_class_model=BDOClass,
        class_image_fn=get_bdo_class_image_url,
    )
    response_serializer = NewCharacterResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


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
    payload, status_code = DeleteCharacterUseCase().execute(
        user=user,
        character_id=id,
        character_model=Character,
    )
    response_serializer = DeleteCharacterResponseSerializer(payload)
    return JsonResponse(response_serializer.data, status=status_code)


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
