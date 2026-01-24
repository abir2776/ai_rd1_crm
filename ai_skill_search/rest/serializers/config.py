from rest_framework import serializers

from ai_skill_search.models import AISkillSearchConfig
from organizations.models import OrganizationPlatform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer


class SkillSearchConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)
    platform = MyPlatformSerializer(read_only=True)

    class Meta:
        model = AISkillSearchConfig
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
        user = self.context["request"].user
        organization = user.get_organization()
        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if not platform:
            raise serializers.ValidationError("Invalid platform uid")
        return AISkillSearchConfig.objects.create(
            organization=organization, platform=platform, **validated_data
        )
