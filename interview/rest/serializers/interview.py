import requests
from rest_framework import serializers

from interview.models import (
    AIPhoneCallConfig,
    InterviewCallConversation,
    InterviewTaken,
)
from organizations.models import Organization


class InterviewCallConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewCallConversation
        fields = "__all__"


class InterviewTakenSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True, required=False)
    interview_data = serializers.SerializerMethodField()

    class Meta:
        model = InterviewTaken
        fields = "__all__"
        read_only_fields = ["organization"]

    def get_interview_data(self, _object):
        data = InterviewCallConversation.objects.filter(interview_id=_object.id).first()
        if data:
            return InterviewTakenSerializer(data).data
        return {}

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id")

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise serializers.ValidationError(
                {"organization_id": "No organization found with this given ID."}
            )

        try:
            config = AIPhoneCallConfig.objects.get(organization_id=organization_id)
        except AIPhoneCallConfig.DoesNotExist:
            raise serializers.ValidationError(
                {"details": "No config found for this organization."}
            )
        status = validated_data.get("ai_decision")
        application_id = validated_data.get("application_id")
        interview = InterviewTaken.objects.create(
            organization=organization, **validated_data
        )
        if application_id:
            jobadder_api_url = f"{config.platform.base_url}/{application_id}"
            if status == "successful":
                status_id = config.status_for_successful_call
            elif status == "unsuccessful":
                status_id = config.status_for_unsuccessful_call
            else:
                status_id = None

            if status_id:
                headers = {
                    "Authorization": f"Bearer {config.platform.access_token}",
                    "Content-Type": "application/json",
                }
                payload = {"statusId": status_id}

                try:
                    response = requests.put(
                        jobadder_api_url, json=payload, headers=headers, timeout=10
                    )
                    response.raise_for_status()
                except requests.RequestException as e:
                    raise serializers.ValidationError(
                        {"jobadder_api": f"Failed to update JobAdder status: {str(e)}"}
                    )

        return interview
