from rest_framework import serializers

from subscription.models import PlanFeature, Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_feature_uid = serializers.CharField(write_only=True)

    class Meta:
        model = Subscription
        fields = [
            "uid",
            "organization",
            "plan_feature",
            "available_limit",
            "status",
            "auto_renew",
            "plan_feature_uid",
        ]
        read_only_fields = ["uid", "organization", "plan_feature", "available_limit"]

    def create(self, validated_data):
        plan_feature_uid = validated_data.pop("plan_feature_uid")
        user = self.context["request"].user
        organization = user.get_organization()
        plan_feature = PlanFeature.objects.filter(uid=plan_feature_uid).first()
        if not plan_feature:
            raise serializers.ValidationError(
                "Plan feature not found with this given uid."
            )
        subscription = Subscription.objects.create(
            organization=organization, plan_feature=plan_feature, available_limit=120
        )
        return subscription
