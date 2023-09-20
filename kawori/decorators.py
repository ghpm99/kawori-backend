from base64 import b64decode
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User

from rest_framework_simplejwt.tokens import AccessToken


def add_cors_react_dev(func):
    def add_cors_react_dev_response(response):

        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = '*'
        response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, *'

        return response

    def inner(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            return add_cors_react_dev_response(HttpResponse('Ok'))

        result = add_cors_react_dev_response(func(request, *args, **kwargs))
        return result

    return inner


def validate_user(func):
    '''
        `validate_user` is a decorator that blocks users that are not active or staff.

        - It's necessary to pass user `id` and `username` in the header authorization.
        Example: `Authorization: Basic <base64(user_id|username)>`;
        - It's necessary to pass the parameter `user` on the view where this decorator will be called,
        even if this parameter will be not used.
    '''

    def inner(request, *args, **kwargs):
        try:
            user_data = request.META.get('HTTP_AUTHORIZATION')[6:] if request.META.get('HTTP_AUTHORIZATION') else None

            if not user_data:
                return JsonResponse({
                    'msg': 'Empty authorization.'
                }, status=403)

            user_id, username = b64decode(user_data).decode('utf-8').split('|')
            user = User.objects.filter(id=user_id, username=username, is_active=True).first()

            if not user:
                return JsonResponse({'msg': 'User not found.'}, status=401)
        except Exception:
            return JsonResponse({
                'msg': 'Error processing user data.',
                'input': b64decode(user_data).decode('utf-8'),
                'expected_input': 'base64(<user_id>|<username>)',
            }, status=500)

        return func(request, user=user, *args, **kwargs)

    return inner


def validate_super_user(func):
    '''
        `validate_user` is a decorator that blocks users that are not active or staff.

        - It's necessary to pass user `id` and `username` in the header authorization.
        Example: `Authorization: Basic <base64(user_id|username)>`;
        - It's necessary to pass the parameter `user` on the view where this decorator will be called,
        even if this parameter will be not used.
    '''

    def inner(request, *args, **kwargs):
        try:
            user_data = request.META.get('HTTP_AUTHORIZATION')[6:] if request.META.get('HTTP_AUTHORIZATION') else None

            if not user_data:
                return JsonResponse({
                    'msg': 'Empty authorization.'
                }, status=403)

            user_id, username = b64decode(user_data).decode('utf-8').split('|')
            user = User.objects.filter(id=user_id, username=username, is_active=True, is_superuser=True).first()

            if not user:
                return JsonResponse({'msg': 'User not found.'}, status=401)
        except Exception:
            return JsonResponse({
                'msg': 'Error processing user data.',
                'input': b64decode(user_data).decode('utf-8'),
                'expected_input': 'base64(<user_id>|<username>)',
            }, status=500)

        return func(request, user=user, *args, **kwargs)

    return inner


def validate_token(func):
    '''
        `validate_token` is a decorator to check if a bearer token is valid and is active.

        - It's necessary to pass user the bearer token in the header authorization.
        Example: `Authorization: Bearer <token>`;
        - The access token can be obtained on the path `/auth/token/` on the API;
        - It's necessary to pass the parameter `user` on the view where this decorator will be called,
        even if this parameter will be not used.
    '''

    def inner(request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION')[7:] if request.META.get('HTTP_AUTHORIZATION') else None
        user_data = {}

        if not token:
            return JsonResponse({'msg': 'Empty authorization.'}, status=403)

        try:
            user_data = AccessToken(token)
        except Exception as err:
            return JsonResponse({'msg': str(err)}, status=401)

        user_id = user_data.get('user_id')
        user = User.objects.get(id=user_id)

        if not user:
            return JsonResponse({'msg': 'User not found.'}, status=404)

        if not user.is_active:
            return JsonResponse({'msg': 'User not active.'}, status=403)

        return func(request, user=user, *args, **kwargs)

    return inner


def validate_token_admin(func):
    '''
        `validate_token_admin` is a decorator to check if a bearer token is valid and is active.

        - It's necessary to pass user the bearer token in the header authorization.
        Example: `Authorization: Bearer <token>`;
        - The access token can be obtained on the path `/auth/token/` on the API;
        - It's necessary to pass the parameter `user` on the view where this decorator will be called,
        even if this parameter will be not used.
    '''

    def inner(request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION')[7:] if request.META.get('HTTP_AUTHORIZATION') else None
        user_data = {}

        if not token:
            return JsonResponse({'msg': 'Empty authorization.'}, status=403)

        try:
            user_data = AccessToken(token)
        except Exception as err:
            return JsonResponse({'msg': str(err)}, status=401)

        user_id = user_data.get('user_id')
        user = User.objects.get(id=user_id)

        if not user:
            return JsonResponse({'msg': 'User not found.'}, status=404)

        if not user.is_active:
            return JsonResponse({'msg': 'User not active.'}, status=403)

        if not user.is_staff:
            return JsonResponse({'msg': 'Este usuário não possui permissão para acessar este módulo.'}, status=403)

        return func(request, user=user, *args, **kwargs)

    return inner
