from rest_framework import serializers
from organizations.models import OrganizationUser


class OrganizationUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "organization",
            "user",
            "role",
            "is_active",
            "joined_at",
            "last_active",
        ]
        read_only_fields = ("__all__",)
