from rest_framework import serializers

from subscription.models import PlanFeature


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = "__all__"
        read_only_fields = []
