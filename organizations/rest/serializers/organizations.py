from rest_framework import serializers

from common.serializers import OrganizationSlimSerializer
from organizations.models import Organization, OrganizationUser


class OrganizationSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    first_name_input = serializers.CharField(write_only=True, required=False)
    last_name_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Organization
        fields = [
            "id",
            "slug",
            "email",
            "phone",
            "website",
            "address",
            "country",
            "description",
            "logo",
            "name",
            "status",
            "first_name",
            "last_name",
            "first_name_input",
            "last_name_input",
        ]
        read_only_fields = ["id", "slug", "logo", "status"]

    def get_first_name(self, obj):
        return self.context["request"].user.first_name

    def get_last_name(self, obj):
        return self.context["request"].user.last_name

    def update(self, instance, validated_data):
        first_name = validated_data.pop("first_name_input", None)
        last_name = validated_data.pop("last_name_input", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        user = self.context["request"].user
        updated = False
        if first_name is not None:
            user.first_name = first_name
            updated = True
        if last_name is not None:
            user.last_name = last_name
            updated = True
        if updated:
            user.save()

        return instance


class MyOrganizationsSerializer(serializers.ModelSerializer):
    organization = OrganizationSlimSerializer(read_only=True)

    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "uid",
            "organization",
            "role",
            "is_active",
            "joined_at",
            "last_active",
        ]
        read_only_fields = ("__all__",)
