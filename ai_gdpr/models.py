from django.db import models

from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform

from .choices import Interval, ProgressStatus


class GDPREmailConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    should_use_last_application_date = models.BooleanField(default=False)
    should_use_last_placement_date = models.BooleanField(default=False)
    should_use_last_note_creatation_date = models.BooleanField(default=False)
    should_use_activity_creation_date = models.BooleanField(default=False)
    should_use_candidate_update_date = models.BooleanField(default=False)
    interval_from_last_action = models.CharField(
        max_length=20,
        choices=Interval.choices,
    )

    def __str__(self):
        return super().__str__()


class GDPREmailTracker(BaseModelWithUID):
    email = models.CharField(max_length=255, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    config = models.ForeignKey(GDPREmailConfig, on_delete=models.CASCADE)
    candidate_id = models.PositiveIntegerField()
    ai_instruction = models.TextField()
    conversation_json = models.JSONField(
        help_text="Conversation messages in JSON format"
    )
    message_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=ProgressStatus.choices,
        default=ProgressStatus.INITIATED,
    )
    ai_dicision = models.CharField(max_length=100, null=True, blank=True)
    is_candidate_agree = models.BooleanField()

    def __str__(self):
        return f"Conversation {self.email} - {self.candidate_id}"
