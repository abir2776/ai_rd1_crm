from rest_framework import serializers
from versatileimagefield.serializers import VersatileImageFieldSerializer

from core.models import User
from organizations.models import Organization


class UserSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["uid", "first_name", "last_name", "email", "phone"]


class OrganizationSlimSerializer(serializers.ModelSerializer):
    logo = VersatileImageFieldSerializer(
        read_only=True,
        sizes=[
            ("full_size", "url"),
            ("thumbnail", "thumbnail__100x100"),
            ("medium_square_crop", "crop__400x400"),
            ("small_square_crop", "crop__50x50"),
        ],
    )

    class Meta:
        model = Organization
        fields = ["uid", "name", "slug", "website", "address", "country", "logo"]
