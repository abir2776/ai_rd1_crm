from django.db import models

from awr_compliance.choices import Interval
from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform


class AWRConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    interval = models.CharField(
        max_length=20,
        choices=Interval.choices,
    )

    def __str__(self):
        return f"{self.organization.name}-{self.interval}"


class AWRTracker(BaseModelWithUID):
    config = models.ForeignKey(AWRConfig, on_delete=models.CASCADE)
    email = models.CharField()

    def __str__(self):
        return f"{self.email}"
