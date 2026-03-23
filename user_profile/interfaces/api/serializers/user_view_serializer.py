from rest_framework import serializers


class UserViewSerializer(serializers.Serializer):
    def to_representation(self, user):
        return {
            "id": user.id,
            "name": user.get_full_name(),
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "last_login": user.last_login,
            "date_joined": user.date_joined,
        }
