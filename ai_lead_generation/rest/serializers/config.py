from rest_framework import serializers

from ai_lead_generation.models import LeadGenerationConfig, MarketingAutomationConfig
from organizations.models import OrganizationPlatform


class LeadGenerationConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)

    class Meta:
        model = LeadGenerationConfig
        fields = "__all__"
        read_only_fields = [
            "id",
            "organization",
            "platform",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        platform_uid = validated_data.pop("platform_uid")
        organization = self.context["request"].user
        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        config = LeadGenerationConfig.objects.create(
            platform=platform, organization=organization, **validated_data
        )
        return config


class MarketingAutomationConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)

    class Meta:
        model = MarketingAutomationConfig
        fields = "__all__"
        read_only_fields = [
            "id",
            "organization",
            "platform",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        platform_uid = validated_data.pop("platform_uid")
        organization = self.context["request"].user.get_organization()
        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        config = MarketingAutomationConfig.objects.create(
            platform=platform, organization=organization, **validated_data
        )
        return config
