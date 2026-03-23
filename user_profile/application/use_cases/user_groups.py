from user_profile.interfaces.api.serializers.user_groups_serializer import UserGroupsSerializer


class UserGroupsUseCase:
    def execute(self, user):
        group_names = [group.name for group in user.groups.all()]
        return UserGroupsSerializer(group_names).data
