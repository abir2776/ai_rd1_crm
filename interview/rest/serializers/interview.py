from rest_framework import serializers

from interview.models import InterviewTaken


class InterviewTakenSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewTaken
        fields = "__all__"
        read_only_fields = []

    def create(self, validated_data):
        user = self.context["request"].user
        organization = user.get_organization()
        interview = InterviewTaken.objects.create(
            **validated_data, organization=organization
        )
        return interview
