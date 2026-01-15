from rest_framework import serializers

from subscription.models import PlanFeature
from subscription.rest.serializers.feature import FeatureSerializer


class PlanFeatureSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(read_only=True)

    class Meta:
        model = PlanFeature
        fields = "__all__"
        read_only_fields = []
