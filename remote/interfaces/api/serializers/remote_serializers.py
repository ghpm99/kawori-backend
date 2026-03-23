from rest_framework import serializers


class SendCommandPayloadSerializer(serializers.Serializer):
    cmd = serializers.JSONField(required=False)


class HotkeyPayloadSerializer(serializers.Serializer):
    hotkey = serializers.JSONField(required=False)


class KeyPressPayloadSerializer(serializers.Serializer):
    keys = serializers.JSONField(required=False)


class MouseMovePayloadSerializer(serializers.Serializer):
    x = serializers.JSONField(required=False)
    y = serializers.JSONField(required=False)
