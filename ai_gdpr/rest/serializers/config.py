from rest_framework import serializers

from ai_gdpr.models import GDPREmailConfig
from organizations.models import OrganizationPlatform


class GDPREmailConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)

    class Meta:
        model = GDPREmailConfig
        fields = "__all__"
        read_only_fields = ["id", "uid", "platform", "organization"]

    def create(self, validated_data):
        platform_uid = validated_data.pop("platform_uid")
        user = self.context["request"].user
        organization = user.get_organization()
        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        return GDPREmailConfig.objects.create(
            organization=organization, platform=platform, **validated_data
        )
