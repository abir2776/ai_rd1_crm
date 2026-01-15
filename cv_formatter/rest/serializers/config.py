from rest_framework import serializers

from cv_formatter.models import CVFormatterConfig
from organizations.models import OrganizationPlatform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer


class CVformatterConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)
    platform = MyPlatformSerializer(read_only=True)

    class Meta:
        model = CVFormatterConfig
        fields = "__all__"
        read_only_fields = ["id", "uid", "organization", "platform"]

    def create(self, validated_data):
        platform_uid = validated_data.pop("platform_uid")
        user = self.context["request"].user
        organization = user.get_organization()
        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        config = CVFormatterConfig.objects.create(
            platform=platform, organization=organization, **validated_data
        )
        return config
