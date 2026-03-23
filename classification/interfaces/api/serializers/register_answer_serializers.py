from rest_framework import serializers


class RegisterAnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.JSONField(required=False)
    combat_style = serializers.JSONField(required=False)
    bdo_class_id = serializers.JSONField(required=False)
    vote = serializers.JSONField(required=False)
