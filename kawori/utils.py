import os

from PIL import Image
from datetime import datetime

from django.core.paginator import Paginator
from django.conf import settings

CLASSES_SYMBOL_SPR_URL = os.path.join(settings.MEDIA_ROOT, "bdoclass/classes_symbol_spr.png")
CLASS_SYMBOL_SPR_PIXEL = 50

CLASSES_IMAGE_SPR_URL = os.path.join(settings.MEDIA_ROOT, "classimage/classes_spr.jpg")
CLASS_IMAGE_SPR_PIXEL_X = 237
CLASS_IMAGE_SPR_PIXEL_Y = 329

DEFAULT_PAGINATION_PER_PAGE = 15


def paginate(object_list: list, page_number: int, per_page: int = DEFAULT_PAGINATION_PER_PAGE) -> dict:
    """
    "paginate" generates a default pattern to API paginations using Django Paginator.

    Parameters:
        - object_list (list): Data that will be divided into pages;
        - page_number (int): Data from which page will be get;
        - per_page (int): Itens per page.

    Returns:
        - data (dict): Dict containing page information and dataset.
    """

    paginator = Paginator(object_list, per_page)
    page = paginator.get_page(page_number)
    result = page.__dict__.get("object_list")

    return {
        "current_page": page.number,
        "total_pages": paginator.num_pages,
        "has_previous": page.has_previous(),
        "has_next": page.has_next(),
        "data": result,
    }


def format_date(string_date: str) -> datetime:
    try:
        return datetime.strptime(string_date, "%Y-%m-%d")
    except Exception:
        return None


def boolean(string: str) -> bool:
    try:
        string = int(string)

        if string == 0:
            return False
        if string == 1:
            return True
    except Exception:
        if isinstance(string, str):
            if string.lower() in ["0", "no", "false"]:
                return False
            if string.lower() in ["1", "yes", "true"]:
                return True


def get_symbol_class(order: int) -> Image:
    image = Image.open(CLASSES_SYMBOL_SPR_URL)
    x = 50
    y = (order * CLASS_SYMBOL_SPR_PIXEL) - CLASS_SYMBOL_SPR_PIXEL

    image_crop_box = (x, y, x + CLASS_SYMBOL_SPR_PIXEL, y + CLASS_SYMBOL_SPR_PIXEL)

    class_image = image.crop(image_crop_box)
    return class_image


def get_image_class(order: int) -> Image:
    image = Image.open(CLASSES_IMAGE_SPR_URL)
    x = CLASS_IMAGE_SPR_PIXEL_X * ((order - 1) % 10)
    y = (int((order - 1) / 10)) * CLASS_IMAGE_SPR_PIXEL_Y

    image_crop_box = (x, y, x + CLASS_IMAGE_SPR_PIXEL_X, y + CLASS_IMAGE_SPR_PIXEL_Y)
    print(image_crop_box)

    class_image = image.crop(image_crop_box)
    return class_image
