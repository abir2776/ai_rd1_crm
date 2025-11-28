from rest_framework import serializers

from interview.models import PrimaryQuestion


class PrimaryQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrimaryQuestion
        fields = "__all__"
