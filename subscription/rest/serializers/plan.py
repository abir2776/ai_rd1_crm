from rest_framework import serializers

from subscription.models import PlanFeature, SubscriptionPlan
from subscription.rest.serializers.feature import FeatureSerializer


class PlanSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
        read_only_fields = []


class PlanFeatureSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(read_only=True)
    plan = PlanSlimSerializer(read_only=True)

    class Meta:
        model = PlanFeature
        fields = "__all__"
        read_only_fields = []
