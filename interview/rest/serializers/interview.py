from rest_framework import serializers

from interview.models import InterviewTaken


class InterviewTakenSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewTaken
        fields = "__all__"
        read_only_fields = []
