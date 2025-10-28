from rest_framework import serializers

from organizations.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

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

    def get_first_name(self, obj):
        return self.context["request"].user.first_name

    def get_last_name(self, obj):
        return self.context["request"].user.last_name
