from django.db import models

from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform


class LeadGenerationConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name}-{self.platform.platform.name}"
