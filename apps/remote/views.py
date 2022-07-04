import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from lib import pusher
from remote.models import Config, Screenshot
from kawori.decorators import add_cors_react_dev, validate_user
from django.views.decorators.http import require_POST, require_GET
from django.core.files import File
from django.conf import settings
import os


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def send_command_view(request, user):
    pusher.send_command(json.loads(request.body).get('cmd'))
    return JsonResponse({'msg': 'ok'})


@add_cors_react_dev
@require_GET
@validate_user
def screen_size_view(request, user):
    screen_size = get_object_or_404(Config, type=Config.CONFIG_SCREEN)
    data = json.loads(screen_size.value)
    return JsonResponse(data)


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def hotkey_view(request, user):
    data = json.loads(request.body)
    hotkey = data.get('hotkey')
    pusher.send_hotkey(hotkey)
    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def key_press_view(request, user):
    data = json.loads(request.body)
    keys = data.get('keys')
    pusher.send_key_press(keys)
    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def mouse_move_view(request, user):
    data = json.loads(request.body)
    x = data.get('x')
    y = data.get('y')
    pusher.mouse_move(x, y)
    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def mouse_button_view(request, user):
    data = json.loads(request.body)
    button = data.get('button')
    pusher.mouse_button(button)
    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def save_screenshot_view(request, user):
    req_files = request.FILES
    if not req_files.get('image'):
        return JsonResponse({'msg': 'Nao existe nenhuma imagem anexo'}, status=400)

    fullname = os.path.join(settings.MEDIA_ROOT, 'screenshot/screenshot.png')

    if os.path.exists(fullname):
        os.remove(fullname)

    file = request.FILES.get('image').file

    screenshot = Screenshot.objects.filter(id=1).first()

    if screenshot is None:
        screenshot = Screenshot()

    screenshot.image.save('screenshot.png', File(file), save=True)

    pusher.notify_screenshot()

    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def mouse_scroll_view(request, user):
    data = json.loads(request.body)
    value = data.get('value')
    pusher.mouse_scroll(value)
    return JsonResponse({'msg': 'Ok'})


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_user
def mouse_move_and_button(request, user):
    data = json.loads(request.body)
    x = data.get('x')
    y = data.get('y')
    button = data.get('button')
    pusher.mouse_move_button(x, y, button)
    return JsonResponse({'msg': 'Ok'})


@add_cors_react_dev
@require_GET
@validate_user
def keyboard_keys(request, user):
    keys = ['\t', '\n', '\r', ' ', '!', '"', '#', '$', '%', '&', "'", '(',
            ')', '*', '+', ',', '-', '.', '/', '0', '1', '2', '3', '4', '5', '6', '7',
            '8', '9', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '_', '`',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o',
            'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '{', '|', '}', '~',
            'accept', 'add', 'alt', 'altleft', 'altright', 'apps', 'backspace',
            'browserback', 'browserfavorites', 'browserforward', 'browserhome',
            'browserrefresh', 'browsersearch', 'browserstop', 'capslock', 'clear',
            'convert', 'ctrl', 'ctrlleft', 'ctrlright', 'decimal', 'del', 'delete',
            'divide', 'down', 'end', 'enter', 'esc', 'escape', 'execute', 'f1', 'f10',
            'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f2', 'f20',
            'f21', 'f22', 'f23', 'f24', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9',
            'final', 'fn', 'hanguel', 'hangul', 'hanja', 'help', 'home', 'insert', 'junja',
            'kana', 'kanji', 'launchapp1', 'launchapp2', 'launchmail',
            'launchmediaselect', 'left', 'modechange', 'multiply', 'nexttrack',
            'nonconvert', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6',
            'num7', 'num8', 'num9', 'numlock', 'pagedown', 'pageup', 'pause', 'pgdn',
            'pgup', 'playpause', 'prevtrack', 'print', 'printscreen', 'prntscrn',
            'prtsc', 'prtscr', 'return', 'right', 'scrolllock', 'select', 'separator',
            'shift', 'shiftleft', 'shiftright', 'sleep', 'space', 'stop', 'subtract', 'tab',
            'up', 'volumedown', 'volumemute', 'volumeup', 'win', 'winleft', 'winright', 'yen',
            'command', 'option', 'optionleft', 'optionright']

    return JsonResponse({'data': keys})
