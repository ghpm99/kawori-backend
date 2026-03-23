from rest_framework import serializers


class GetBDOClassQuerySerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)


class GetBDOClassResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class GetFacetextureConfigResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class SaveDetailRequestSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        return data


class SaveDetailResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class ChangeShowClassIconRequestSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        return data


class ChangeShowClassIconResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class ClassAssetPathSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class ClassAssetErrorResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class ChangeCharacterNameRequestSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        return data


class ChangeCharacterNameResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
