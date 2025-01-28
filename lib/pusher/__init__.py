import os
from django.http import JsonResponse
from django.conf import settings
import pusher
from remote.models import Config


pusher_client = pusher.Pusher(
    app_id=settings.ENV_PUSHER_APP_ID,
    key=settings.ENV_PUSHER_KEY,
    secret=settings.ENV_PUSHER_SECRET,
    cluster=settings.ENV_PUSHER_CLUSTER,
    ssl=True,
)


def send_command(command):
    pusher_client.trigger("private-display", "command", {"cmd": command})


def channel_occupied(event):
    if event["channel"] == "private-status":
        pusher_client.trigger("private-events", "status-channel", {"occupied": True})
    elif event["channel"] == "private-remote":
        pusher_client.trigger("private-events", "remote-channel", {"occupied": True})


def channel_vacated(event):
    if event["channel"] == "private-status":
        pusher_client.trigger("private-events", "status-channel", {"occupied": False})
    elif event["channel"] == "private-remote":
        pusher_client.trigger("private-events", "remote-channel", {"occupied": False})


def client_event(event):
    if event["event"] == "client-screen":
        data = event["data"]
        config = Config.objects.filter(type=Config.CONFIG_SCREEN).first()
        if config is None:
            screen_data = Config(type=Config.CONFIG_SCREEN, value=data)
            screen_data.save()
            return
        config.value = data
        config.save()


def webhook(request):
    webhook = pusher_client.validate_webhook(
        key=request.headers.get("X-Pusher-Key"), signature=request.headers.get("X-Pusher-Signature"), body=request.body
    )

    if webhook is None:
        return JsonResponse({"msg": "Webhook incorreto"}, status=400)

    for event in webhook["events"]:
        if event["name"] == "channel_occupied":
            channel_occupied(event)
        elif event["name"] == "channel_vacated":
            channel_vacated(event)
        elif event["name"] == "client_event":
            client_event(event)

    return JsonResponse({"msg": "ok"})


def auth(request, channel_name, socket_id):
    auth_response = pusher_client.authenticate(channel=channel_name, socket_id=socket_id)
    return JsonResponse(auth_response)


def send_hotkey(hotkey):
    pusher_client.trigger("private-display", "hotkey", {"hotkey": hotkey})


def send_key_press(keys):
    pusher_client.trigger("private-display", "keypress", {"keys": keys})


def mouse_move(x, y):
    pusher_client.trigger("private-display", "mouse-move", {"x": x, "y": y})


def mouse_button(button):
    pusher_client.trigger("private-display", "mouse-button", {"button": button})


def notify_screenshot():
    pusher_client.trigger("private-remote", "new-screenshot", {})


def mouse_scroll(value):
    pusher_client.trigger("private-display", "scroll", {"value": value})


def mouse_move_button(x, y, button):
    pusher_client.trigger("private-display", "mouse-move-button", {"x": x, "y": y, "button": button})
