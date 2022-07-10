from django.views.decorators.csrf import csrf_exempt
from kawori.decorators import add_cors_react_dev, validate_super_user
from django.views.decorators.http import require_POST
from lib import pusher


@csrf_exempt
@add_cors_react_dev
@require_POST
def pusher_webhook(request):
    return pusher.webhook(request)


@csrf_exempt
@add_cors_react_dev
@require_POST
@validate_super_user
def pusher_auth(request, user):
    values = request.body.decode('utf-8').split('&')
    socket_id = ''
    channel_name = ''
    for value in values:
        if(value.startswith('socket_id')):
            socket_id = value.split('=')[1]

        elif(value.startswith('channel_name')):
            channel_name = value.split('=')[1]

    return pusher.auth(request, channel_name, socket_id)
