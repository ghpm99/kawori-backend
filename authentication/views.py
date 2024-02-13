from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from kawori.decorators import add_cors_react_dev, validate_user
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
import json
import base64


@csrf_exempt
@add_cors_react_dev
@require_POST
def signin_view(request):
    data = json.loads(request.body)
    if 'credentials' in data:
        username = data['credentials']['username']
        password = data['credentials']['password']
        user = authenticate(
            username=username,
            password=password
        )
        if user is not None:
            return JsonResponse({
                'token': base64.b64encode(bytes(f'{user.id}|{user.username}', 'utf-8')).decode('ascii')
            })
        else:
            return JsonResponse({'msg': 'user not found'}, status=404)

    return JsonResponse({'msg': 'credentials is missing'}, status=400)


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_GET
def user_view(request, user):

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
def signup_view(request):
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
