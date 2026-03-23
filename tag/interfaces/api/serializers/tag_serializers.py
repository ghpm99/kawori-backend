from rest_framework import serializers


class TagListQuerySerializer(serializers.Serializer):
    name__icontains = serializers.CharField(required=False, allow_blank=True)


class TagCreatePayloadSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    color = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )

    def validate(self, attrs):
        name = attrs.get("name")
        color = attrs.get("color")

        if not name or name.strip() == "":
            raise serializers.ValidationError("Nome da tag é obrigatório")

        if name.startswith("#"):
            raise serializers.ValidationError("Nome da tag não pode iniciar com #")

        if not color:
            raise serializers.ValidationError("Cor da tag é obrigatória")

        return attrs
