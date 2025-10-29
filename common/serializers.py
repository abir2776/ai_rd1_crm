from rest_framework import serializers

from core.models import User


class UserSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["uid", "first_name", "last_name", "email", "phone"]
