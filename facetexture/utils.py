import os
from PIL import Image
from django.conf import settings

CLASSES_SYMBOL_SPR_URL = os.path.join(settings.MEDIA_ROOT, 'bdoclass/classes_symbol_spr.png')
CLASS_SYMBOL_SPR_PIXEL = 50

CLASSES_IMAGE_SPR_URL = os.path.join(settings.MEDIA_ROOT, 'classimage/classes_spr.jpg')
CLASS_IMAGE_SPR_PIXEL_X = 237
CLASS_IMAGE_SPR_PIXEL_Y = 329

def get_symbol_class(order: int) -> Image:
    image = Image.open(CLASSES_SYMBOL_SPR_URL)
    x = 0
    y = (order * CLASS_SYMBOL_SPR_PIXEL) -CLASS_SYMBOL_SPR_PIXEL

    image_crop_box = (x, y, x + CLASS_SYMBOL_SPR_PIXEL, y + CLASS_SYMBOL_SPR_PIXEL)

    class_image = image.crop(image_crop_box)
    return class_image


def get_image_class(order: int) -> Image:
    image = Image.open(CLASSES_IMAGE_SPR_URL)
    # calculo calc((100% / 9) * 2) calc((100% / 2) * 2)
    # ()
    x = (CLASS_IMAGE_SPR_PIXEL_X * (order % 10))
    y = (order * CLASS_IMAGE_SPR_PIXEL_Y) -CLASS_IMAGE_SPR_PIXEL_Y

    image_crop_box = (x, y, x + CLASS_IMAGE_SPR_PIXEL_X, y + CLASS_IMAGE_SPR_PIXEL_Y)
    print(image_crop_box)

    class_image = image.crop(image_crop_box)
    return class_image