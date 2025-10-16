from rest_framework import serializers
from organizations.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = ["id", "slug", "logo", "status"]
