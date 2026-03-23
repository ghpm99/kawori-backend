from rest_framework import serializers


class UserGroupsSerializer(serializers.Serializer):
    def to_representation(self, group_names):
        return {"data": group_names}
