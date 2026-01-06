from rest_framework import serializers

from interview.models import (
    AIPhoneCallConfig,
    InterviewCallConversation,
    InterviewTaken,
)
from interview.tasks.ai_phone import update_application_status_after_call
from interview.tasks.ai_sms import send_sms_message
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
            return InterviewCallConversationSerializer(data).data
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
            if status == "successful":
                status_id = config.status_for_successful_call
            elif status == "unsuccessful":
                status_id = config.status_for_unsuccessful_call
            else:
                status_id = None

            if status_id:
                update_application_status_after_call.delay(
                    organization_id, application_id, status_id
                )
            if status == "successful" and config.sent_document_upload_link:
                message = f"Please Upload your updated documents in this link: {config.document_upload_link}"
                send_sms_message.delay(
                    validated_data["candidate_phone"],
                    str(config.phone.phone_number),
                    message,
                    organization_id,
                )

        return interview
