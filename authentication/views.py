import json
from datetime import datetime

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from authentication.utils import get_token
from kawori.decorators import add_cors_react_dev, validate_user


@csrf_exempt
@add_cors_react_dev
@require_POST
def obtain_token_pair(request: HttpRequest) -> JsonResponse:
    req = json.loads(request.body)
    err = []

    if not req.get('username'):
        err.append({'username': 'Este campo é obrigatório'})
    if not req.get('password'):
        err.append({'password': 'Este campo é obrigatório'})
    if err:
        return JsonResponse({'errors': err}, status=400)

    user = authenticate(username=req.get('username'), password=req.get('password'))

    if not user:
        return JsonResponse({'msg': 'Dados incorretos.'}, status=404)
    if not user.is_active:
        return JsonResponse({'msg': 'Este usuário não está ativo.'}, status=403)

    if user.last_login:
        user.last_login = datetime.now(tz=user.last_login.tzinfo)
    else:
        user.last_login = datetime.now(tz=timezone.utc)

    user.save()
    tokens = get_token(user)

    return JsonResponse({'tokens': tokens})


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_GET
def user_view(request: HttpRequest, user: User) -> JsonResponse:

    return JsonResponse({
        'id': user.id,
        'name': user.get_full_name(),
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'last_login': user.last_login,
        'date_joined': user.date_joined,
    })


@csrf_exempt
@add_cors_react_dev
@require_POST
def signup_view(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)

    required_fields = ['username', 'password', 'email', 'name', 'last_name']
    for field in required_fields:
        if not data.get(field):
            return JsonResponse({'msg': 'Todos os campos são obrigatórios.'}, status=400)

    username = data['username']
    password = data['password']
    email = data['email']
    name = data['name']
    last_name = data['last_name']

    username_exists = User.objects.filter(username=username).exists()

    if username_exists:
        return JsonResponse({'msg': 'Usuário já cadastrado'}, status=400)

    email_exists = User.objects.filter(email=email).exists()

    if email_exists:
        return JsonResponse({'msg': 'E-mail já cadastrado'}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email
    )
    user.first_name = name
    user.last_name = last_name
    user.save()
    return JsonResponse({'msg': 'Usuário criado com sucesso!'})
