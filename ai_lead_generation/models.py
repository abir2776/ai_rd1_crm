from django.contrib.postgres.fields import ArrayField
from django.db import models

from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform


class LeadGenerationConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name}-{self.platform.platform.name}"


class MarketingAutomationConfig(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="marketing_automation_configs",
        help_text="Organization this configuration belongs to",
    )

    platform = models.ForeignKey(
        OrganizationPlatform,
        on_delete=models.CASCADE,
        related_name="marketing_automation_configs",
        help_text="Platform/ATS integration to use",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether marketing automation is active for this organization",
    )

    exclude_agencies = models.BooleanField(
        default=True,
        help_text="If True, skip companies identified as recruitment agencies",
    )

    opportunity_stage = models.CharField(
        null=True,
        blank=True,
        help_text="Stage ID to assign to created opportunities (optional)",
    )

    opportunity_owners = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text="List of user IDs who will own the created opportunities",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketing_automation_config"
        verbose_name = "Marketing Automation Config"
        verbose_name_plural = "Marketing Automation Configs"
        unique_together = ["organization", "platform"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return (
            f"Marketing Config - Org: {self.organization_id} (Active: {self.is_active})"
        )
