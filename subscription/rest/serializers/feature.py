from rest_framework import serializers

from subscription.models import Feature, Subscription


class FeatureSerializer(serializers.ModelSerializer):
    is_purchased = serializers.SerializerMethodField()

    class Meta:
        model = Feature
        fields = "__all__"
        read_only_fields = []

    def get_is_purchased(self, obj):
        subscription = Subscription.objects.filter(plan_feature__feature_id=obj.id)
        if subscription.exists():
            return True
        else:
            return False
