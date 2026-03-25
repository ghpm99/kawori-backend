from user_profile.interfaces.api.serializers.user_view_serializer import (
    UserViewSerializer,
)


class UserViewUseCase:
    def execute(self, user):
        return UserViewSerializer(user).data
