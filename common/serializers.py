from rest_framework import serializers
from versatileimagefield.serializers import VersatileImageFieldSerializer

from core.models import User
from organizations.models import Organization


class UserSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["uid", "first_name", "last_name", "email", "phone"]


class OrganizationSlimSerializer(serializers.ModelSerializer):
    logo = VersatileImageFieldSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = ["uid", "name", "slug", "website", "address", "country", "logo"]
