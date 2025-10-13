from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from common.models import BaseModelWithUID
from common.choices import Status

User = get_user_model()


class Feature(BaseModelWithUID):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
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
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="subscriptions"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.end_date

    def remaining_days(self):
        return max((self.end_date - timezone.now()).days, 0)
