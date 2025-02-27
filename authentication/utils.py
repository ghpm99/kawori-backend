from django.contrib.auth.models import User, Group
from rest_framework_simplejwt.tokens import RefreshToken,AccessToken
from rest_framework.exceptions import AuthenticationFailed


def get_token(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def register_groups(user: User) -> None:
    user_group = Group.objects.filter(name="user").first()

    if user_group is not None:
        user_group.user_set.add(user)

    black_desert_group = Group.objects.filter(name="blackdesert").first()

    if black_desert_group is not None:
        black_desert_group.user_set.add(user)


def refresh_access_token(refresh_token) -> AccessToken:
    refresh = RefreshToken(refresh_token)
    return refresh.access_token
