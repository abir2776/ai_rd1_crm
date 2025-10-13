from rest_framework import serializers
from organizations.models import OrganizationUser
from core.models import User


class OrganizationUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "organization",
            "user",
            "role",
            "title",
            "phone",
            "email",
            "is_active",
            "joined_at",
            "last_active",
        ]
        read_only_fields = [
            "id",
            "joined_at",
            "last_active",
            "organization",
            "user",
            "is_active",
        ]

    def create(self, validated_data):
        request_user = self.context["request"].user
        email = validated_data.get("email")
        phone = validated_data.get("phone")
        user = User.objects.filter(email=email).first()
        if user == None:
            user = User.objects.create(email=email, phone=phone)
        organization = request_user.get_organization()
        return OrganizationUser.objects.create(
            **validated_data, user=user, organization=organization, is_active=False
        )
