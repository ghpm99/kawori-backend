import io
import os
import colorsys

from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import numpy as np
from datetime import datetime
from scipy.ndimage import binary_dilation

from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.conf import settings

from facetexture.models import BDOClass

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


def hex_to_rgb(hex_color: str) -> tuple:
    """
    Converte uma cor hexadecimal para um tuple RGB.

    Args:
        hex_color (str): A cor em formato hexadecimal (ex: "#RRGGBB").

    Returns:
        tuple: Um tuple (R, G, B).
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def apply_glowing_icon(image, hex_color="#C0E0FF", glow_radius=0.5, glow_brightness=6.0):
    """
    Aplica um efeito de brilho colorido a um ícone, colocando-o em um fundo sólido.

    Args:
        image (PIL.Image.Image): A imagem do ícone de entrada (deve ter canal alfa).
        hex_color (str): A cor hexadecimal do brilho (ex: "#RRGGBB").
        glow_radius (int): O raio do desfoque para o brilho.
        glow_brightness (float): A intensidade do brilho.
        background_color (tuple): A cor de fundo da imagem final (RGB ou RGBA).

    Returns:
        PIL.Image.Image: A imagem resultante com o ícone brilhante e o fundo.
    """
    rgb_color = hex_to_rgb(hex_color)
    image = image.convert("RGBA")
    data = np.array(image)
    alpha = data[..., 3] / 255.0  # Normaliza o canal alfa para 0-1

    # Cria a base do ícone colorida para o efeito de brilho.
    # Onde o ícone é opaco, ele terá a cor rgb_color, e a transparência original é mantida.
    colored_icon_base = np.zeros_like(data)
    for i in range(3):  # Para R, G, B
        # Aplica a cor do brilho multiplicada pela opacidade do pixel original
        colored_icon_base[..., i] = (rgb_color[i] * alpha).astype(np.uint8)
    # Mantém o canal alfa original do ícone para a base colorida
    colored_icon_base[..., 3] = (alpha * 255).astype(np.uint8)

    colored_icon_image = Image.fromarray(colored_icon_base, mode="RGBA")

    # Aplica o desfoque para criar o efeito de brilho
    blurred_glow = colored_icon_image.filter(ImageFilter.GaussianBlur(radius=glow_radius))

    # Aumenta o brilho da camada de brilho
    enhanced_glow = ImageEnhance.Brightness(blurred_glow).enhance(glow_brightness)

    # Cria a imagem final com uma cor de fundo sólida
    final = Image.new("RGBA", image.size, (0, 0, 0, 0))
    # Compõe a camada de brilho sobre o fundo
    final = Image.alpha_composite(final, enhanced_glow)

    return final


def apply_vivid_outline_glow(
    image: Image.Image, hex_color="#00FFAA", glow_radius=2, glow_brightness=1.0
) -> Image.Image:
    rgb_color = hex_to_rgb(hex_color)
    image = image.convert("RGBA")
    data = np.array(image)
    alpha = data[..., 3] / 255.0

    # White icon
    white_icon = np.zeros_like(data)
    white_icon[..., :3] = 255
    white_icon[..., 3] = (alpha * 255).astype(np.uint8)
    icon_white = Image.fromarray(white_icon, mode="RGBA")

    # Outline mask
    alpha_mask = (alpha > 0.05).astype(np.uint8)
    outline_mask = binary_dilation(alpha_mask, iterations=2).astype(np.float32) - alpha_mask
    outline_mask = np.clip(outline_mask, 0, 1)

    # Colored outline
    outline_layer = np.zeros_like(data)
    for i in range(3):
        outline_layer[..., i] = (rgb_color[i] * outline_mask).astype(np.uint8)
    outline_layer[..., 3] = (outline_mask * 255).astype(np.uint8)
    colored_outline = Image.fromarray(outline_layer, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=glow_radius))

    blurred_glow = Image.fromarray(outline_layer, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=glow_radius * 2))
    # enhanced_glow = ImageEnhance.Brightness(blurred_glow).enhance(glow_brightness)

    # Composite
    final = Image.new("RGBA", image.size, (0, 0, 0, 0))
    final = Image.alpha_composite(final, blurred_glow)
    final = Image.alpha_composite(final, colored_outline)
    final = Image.alpha_composite(final, icon_white)

    return final


def _prepare_image_and_mask(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    """
    Prepara a imagem de entrada, garantindo que seja RGBA e extraindo sua máscara.

    Args:
        image (Image.Image): A imagem de entrada.

    Returns:
        tuple[Image.Image, Image.Image]: A imagem convertida para RGBA e sua máscara (canal alfa).
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    original_mask = image.split()[-1]
    return image, original_mask


def _create_halo_layer(
    image: Image.Image, original_mask: Image.Image, rgb_color: tuple, glow_radius: int, border_width: int
) -> Image.Image:
    """
    Cria a camada de halo externo suave.

    Args:
        image (Image.Image): A imagem original.
        original_mask (Image.Image): A máscara (canal alfa) da imagem original.
        rgb_color (tuple): A cor RGB do brilho.
        glow_radius (int): O raio do desfoque para o halo.
        border_width (int): A largura da borda (usada no cálculo da expansão).

    Returns:
        Image.Image: A camada de halo.
    """
    expansion_amount = glow_radius + border_width
    halo_layer = Image.new("RGBA", (image.width, image.height), (0, 0, 0, 0))

    colored_shape = Image.new("RGBA", image.size, rgb_color + (255,))
    colored_shape.putalpha(original_mask)

    halo_layer.paste(colored_shape, (0, 0), colored_shape)

    halo_layer = halo_layer.filter(ImageFilter.MaxFilter(expansion_amount * 2 + 1))
    halo_layer = halo_layer.filter(ImageFilter.GaussianBlur(glow_radius))
    return halo_layer


def _create_border_layer(
    image: Image.Image, original_mask: Image.Image, rgb_color: tuple, border_width: int
) -> Image.Image:
    """
    Cria a camada de borda externa mais definida.

    Args:
        image (Image.Image): A imagem original.
        original_mask (Image.Image): A máscara (canal alfa) da imagem original.
        rgb_color (tuple): A cor RGB da borda.
        border_width (int): A largura da borda.

    Returns:
        Image.Image: A camada de borda.
    """
    border_layer = Image.new("RGBA", (image.width, image.height), (0, 0, 0, 0))

    mask_for_border = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask_for_border).bitmap((0, 0), original_mask, fill=255)

    expanded_border_mask = mask_for_border.filter(ImageFilter.MaxFilter(border_width * 2 + 1))

    colored_border_fill = Image.new("RGBA", (image.width, image.height), rgb_color + (255,))

    temp_expanded_mask_full_size = Image.new("L", (image.width, image.height), 0)
    temp_expanded_mask_full_size.paste(expanded_border_mask, (0, 0))

    border_layer.paste(colored_border_fill, (0, 0), temp_expanded_mask_full_size)
    return border_layer.filter(ImageFilter.GaussianBlur(radius=8))


def _create_white_glow_layer(
    image: Image.Image, original_mask: Image.Image, white_glow_intensity: float
) -> Image.Image:
    """
    Cria a camada de brilho branco interno.

    Args:
        image (Image.Image): A imagem original.
        original_mask (Image.Image): A máscara (canal alfa) da imagem original.
        white_glow_intensity (float): A opacidade do brilho branco.

    Returns:
        Image.Image: A camada de brilho branco.
    """

    white_glow_layer = Image.new("RGBA", image.size, (255, 255, 255, 255))
    white_glow_layer.putalpha(original_mask)
    return white_glow_layer


def _compose_layers(
    image: Image.Image, halo_layer: Image.Image, border_layer: Image.Image, white_glow_layer: Image.Image
) -> Image.Image:
    """
    Compõe todas as camadas na imagem final.

    Args:
        image (Image.Image): A imagem original.
        halo_layer (Image.Image): A camada de halo.
        border_layer (Image.Image): A camada de borda.
        white_glow_layer (Image.Image): A camada de brilho branco.

    Returns:
        Image.Image: A imagem final composta.
    """
    final_image_size_width = max(halo_layer.width, border_layer.width)
    final_image_size_height = max(halo_layer.height, border_layer.height)
    final_image = Image.new("RGBA", (final_image_size_width, final_image_size_height), (0, 0, 0, 0))

    # Colar as camadas na ordem correta (de trás para frente)
    final_image.paste(halo_layer, (0, 0), halo_layer)
    final_image.paste(border_layer, (0, 0), border_layer)
    final_image.paste(white_glow_layer, (0, 0), white_glow_layer)
    final_image.paste(image, (0, 0), image)
    return final_image


def _resize_to_original(final_image: Image.Image, original_image_size: tuple) -> Image.Image:
    """
    Redimensiona a imagem final para o tamanho original, se necessário.

    Args:
        final_image (Image.Image): A imagem composta.
        original_image_size (tuple): O tamanho original da imagem de entrada.

    Returns:
        Image.Image: A imagem redimensionada.
    """
    if final_image.size != original_image_size:
        final_image = final_image.resize(original_image_size, Image.LANCZOS)
    return final_image


def apply_glow_effect(
    image: Image.Image,
    hex_color: str,
    glow_radius: int = 3,
    border_width: int = 1,
    white_glow_intensity: float = 0.7,
) -> Image.Image:
    """
    Aplica um efeito de brilho iluminado a uma imagem, com halo externo suave, borda e brilho interno branco.

    Args:
        image (Image.Image): A imagem de entrada (objeto PIL.Image.Image).
        hex_color (str): A cor do brilho em formato hexadecimal (ex: "#ADD8E6").
        glow_radius (int): O raio do desfoque para o efeito de halo externo. Quanto maior, mais espalhado.
                           Este valor agora controla a suavidade do contorno.
        border_width (int): A largura da borda colorida que envolve o halo.
                            Este valor agora controla a espessura do contorno mais definido.
        white_glow_intensity (float): A opacidade da camada de brilho branco interno (0.0 a 1.0).
        output_to_original_size (bool): Se True, a imagem final será redimensionada para o tamanho da imagem original.
                                        Isso pode fazer com que o ícone pareça ligeiramente menor se o brilho for muito grande.

    Returns:
        PIL.Image.Image: A imagem com o efeito de brilho aplicado.
    """
    # Preparar a imagem e a máscara
    image, original_mask = _prepare_image_and_mask(image)
    rgb_color = hex_to_rgb(hex_color)

    # Criar as camadas individuais
    halo_layer = _create_halo_layer(image, original_mask, rgb_color, glow_radius, border_width)
    border_layer = _create_border_layer(image, original_mask, rgb_color, border_width)
    white_glow_layer = _create_white_glow_layer(image, original_mask, white_glow_intensity)

    # Compor todas as camadas
    final_image = _compose_layers(image, halo_layer, border_layer, white_glow_layer)

    return final_image


def get_glowed_symbol_class(bdoClass: BDOClass, class_image: Image.Image) -> Image.Image:
    image_exists = bdoClass.image and bdoClass.image.name and bdoClass.image.storage.exists(bdoClass.image.name)

    if not image_exists:
        class_image = apply_glow_effect(class_image, hex_color=bdoClass.color)
        # buffer = io.BytesIO()
        # class_image.save(buffer, format="PNG")
        # buffer.seek(0)
        # bdoClass.image.save(f"class_{bdoClass.id}_glow.png", ContentFile(buffer.getvalue()), save=True)
    else:
        image_file = bdoClass.image.file
        class_image = Image.open(image_file).convert("RGBA")

    return class_image


def get_symbol_class(bdoClass: BDOClass, symbol_style="D") -> Image.Image:
    image = Image.open(CLASSES_SYMBOL_SPR_URL)

    x = 50 if symbol_style == "G" else 0
    y = (bdoClass.class_order * CLASS_SYMBOL_SPR_PIXEL) - CLASS_SYMBOL_SPR_PIXEL

    image_crop_box = (x, y, x + CLASS_SYMBOL_SPR_PIXEL, y + CLASS_SYMBOL_SPR_PIXEL)

    class_image = image.crop(image_crop_box)

    if symbol_style == "D":
        class_image = get_glowed_symbol_class(bdoClass, class_image)
    class_image.thumbnail((50, 50), Image.Resampling.LANCZOS)
    return class_image


def get_image_class(order: int) -> Image.Image:
    image = Image.open(CLASSES_IMAGE_SPR_URL)
    x = CLASS_IMAGE_SPR_PIXEL_X * ((order - 1) % 10)
    y = (int((order - 1) / 10)) * CLASS_IMAGE_SPR_PIXEL_Y

    image_crop_box = (x, y, x + CLASS_IMAGE_SPR_PIXEL_X, y + CLASS_IMAGE_SPR_PIXEL_Y)

    class_image = image.crop(image_crop_box)
    return class_image
