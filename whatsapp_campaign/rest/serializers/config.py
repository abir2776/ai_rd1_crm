from rest_framework import serializers

from organizations.models import OrganizationPlatform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer
from whatsapp_campaign.models import WhatsAppCampaignConfig


class WhatsAppCampaignConfigSerializer(serializers.ModelSerializer):
    platform = MyPlatformSerializer(read_only=True)

    class Meta:
        model = WhatsAppCampaignConfig
        fields = "__all__"
        read_only_fields = [
            "id",
            "uid",
            "organization",
            "platform",
            "status",
            "total_contacts",
            "messages_sent",
            "messages_failed",
            "messages_delivered",
            "messages_read",
            "responses_received",
            "created_at",
            "updated_at",
            "sent_at",
            "completed_at",
        ]

    def validate(self, data):
        schedule_type = data.get("schedule_type", "now")
        scheduled_at = data.get("scheduled_at")

        if schedule_type == "scheduled" and not scheduled_at:
            raise serializers.ValidationError(
                {
                    "scheduled_at": "This field is required when schedule type is 'scheduled'"
                }
            )

        if schedule_type == "now" and scheduled_at:
            data["scheduled_at"] = None

        contact_filter_type = data.get("contact_filter_type", "all")
        selected_contact_ids = data.get("selected_contact_ids", [])

        if contact_filter_type == "selected" and not selected_contact_ids:
            raise serializers.ValidationError(
                {
                    "selected_contact_ids": "This field is required when contact filter type is 'selected'"
                }
            )

        return data

    def create(self, validated_data):
        platform_uid = validated_data.pop("platform_uid")

        user = self.context["request"].user
        organization = user.get_organization()

        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        return WhatsAppCampaignConfig.objects.create(
            organization=organization, platform=platform, **validated_data
        )
