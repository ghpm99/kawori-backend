from django.contrib.auth.models import User, Group
from rest_framework_simplejwt.tokens import RefreshToken


def get_token(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def get_default_group() -> Group:
    group = Group.objects.filter(name="user").first()

    if group is None:
        group = Group.objects.create(name="user")

    return group