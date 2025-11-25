from django.contrib.auth import get_user_model
from django.db import models

from common.choices import Status
from common.models import BaseModelWithUID
from organizations.models import Organization

from .choices import FeatureType

User = get_user_model()


class Feature(BaseModelWithUID):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=FeatureType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    def __str__(self):
        return self.name


class SubscriptionPlan(BaseModelWithUID):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    def __str__(self):
        return self.name


class PlanFeature(BaseModelWithUID):
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="plan_features"
    )
    feature = models.ForeignKey(
        Feature, on_delete=models.CASCADE, related_name="feature_plans"
    )
    limit = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("plan", "feature")

    def __str__(self):
        return f"{self.plan.name} - {self.feature.name}"


class Subscription(BaseModelWithUID):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan_feature = models.ForeignKey(
        PlanFeature, on_delete=models.CASCADE, related_name="subscriptions"
    )
    available_limit = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name} - {self.plan_feature.feature.name}"
