from rest_framework import serializers

from subscription.models import SubscriptionPlan,Subscription


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
        read_only_fields = []
        
        
class SubscriptionSerializer(serializers.ModelSerializer):
    plan_feature_uid = serializers.CharField(write_only=True)
    
    class Meta:
        model = Subscription
        fields = "__all__"
        read_only_fields = []