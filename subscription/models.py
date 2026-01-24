from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models

from common.choices import Status
from common.models import BaseModelWithUID
from organizations.models import Organization

from .choices import FeatureType

User = get_user_model()


class Category(BaseModelWithUID):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Feature(BaseModelWithUID):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=50, choices=FeatureType.choices)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    def __str__(self):
        return self.name


class PlanFeature(BaseModelWithUID):
    feature = models.ForeignKey(
        Feature, on_delete=models.CASCADE, related_name="feature_plans"
    )
    limit = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    usage_fee_included = models.BooleanField(default=True)
    des_list = ArrayField(models.CharField(max_length=255), blank=True, default=list)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        unique_together = ["feature", "name"]

    def __str__(self):
        return f"{self.name} - {self.feature.name}"


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
