from rest_framework import serializers

from common.serializers import UserSlimSerializer
from organizations.models import OrganizationUser


class OrganizationUserSerializer(serializers.ModelSerializer):
    user = UserSlimSerializer(read_only=True)

    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "uid",
            "organization",
            "user",
            "role",
            "is_active",
            "joined_at",
            "last_active",
        ]
        read_only_fields = ("__all__",)
