from rest_framework import serializers

from ai_gdpr.models import GDPREmailConfig
from organizations.models import OrganizationPlatform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer


class GDPREmailConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True, required=False)
    platform = MyPlatformSerializer(read_only=True)

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
            raise serializers.ValidationError({"platform_uid": "Invalid platform uid"})

        return GDPREmailConfig.objects.create(
            organization=organization, platform=platform, **validated_data
        )

    def update(self, instance, validated_data):
        platform_uid = validated_data.pop("platform_uid", None)

        if platform_uid:
            platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
            if not platform:
                raise serializers.ValidationError(
                    {"platform_uid": "Invalid platform uid"}
                )
            instance.platform = platform

        # update remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
