from django.db import models

from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform


class AWRConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    selected_status_ids = models.JSONField(
        default=list, help_text="List of status IDs to filter placements"
    )
    selected_payment_types = models.JSONField(
        default=list, help_text="List of payment type names to filter placements"
    )
    placement_started_before_days = models.IntegerField(
        default=84,
        help_text="Number of days before which placement should have started (minimum 7)",
    )
    email_template_name = models.CharField(
        max_length=255,
        default="emails/awr_compliance_email.html",
        help_text="Email template to use",
    )
    email_sender = models.EmailField(
        help_text="Email address to send from", null=True, blank=True
    )
    email_reply_to = models.EmailField(
        help_text="Email address to receive replies", null=True, blank=True
    )

    def __str__(self):
        return f"{self.organization.name} - AWR Config"


class AWRTracker(BaseModelWithUID):
    config = models.ForeignKey(AWRConfig, on_delete=models.CASCADE)
    placement_id = models.IntegerField(help_text="Placement ID from platform")
    contact_email = models.EmailField(help_text="Contact email from placement")
    last_sent_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["config", "placement_id"]

    def __str__(self):
        return f"Placement {self.placement_id} - {self.contact_email}"
