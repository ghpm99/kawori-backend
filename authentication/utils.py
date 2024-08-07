from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken


def get_token(user: User) -> dict:
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
