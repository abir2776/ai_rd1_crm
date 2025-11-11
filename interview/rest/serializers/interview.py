from rest_framework import serializers

from interview.models import InterviewTaken
from organizations.models import Organization


class InterviewTakenSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = InterviewTaken
        fields = "__all__"
        read_only_fields = ["organization"]

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id")

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise serializers.ValidationError(
                {"organization_id": "No organization found with this given ID."}
            )
        interview = InterviewTaken.objects.create(
            organization=organization, **validated_data
        )
        return interview
