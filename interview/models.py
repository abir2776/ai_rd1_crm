from django.db import models

from common.choices import Status
from common.models import BaseModelWithUID
from organizations.models import Organization


class InterviewType(BaseModelWithUID):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.ACTIVE
    )

    def __str__(self):
        return self.name


class InterviewTaken(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    company_id = models.PositiveIntegerField()
    application_id = models.PositiveIntegerField()
    candidate_id = models.PositiveIntegerField()
    job_id = models.PositiveIntegerField()
    interview_type = models.ForeignKey(InterviewType, on_delete=models.CASCADE)
    interview_status = models.CharField(max_length=100)
    ai_dicision = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    call_sid = models.CharField(max_length=100)
    call_duration = models.CharField(max_length=100)
    call_status = models.CharField(max_length=100)
    disconnection_reason = models.CharField(max_length=100)

    def __str__(self):
        return f"company_id: {self.company_id} - application_id: {self.application_id} - interview_type: {self.interview_type.name}"


class InterviewConversation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    call_sid = models.CharField(max_length=100, unique=True)
    application_id = models.PositiveIntegerField()
    candidate_id = models.PositiveIntegerField()
    job_id = models.PositiveIntegerField()

    conversation_text = models.TextField(help_text="Full conversation in text format")
    conversation_json = models.JSONField(
        help_text="Conversation messages in JSON format"
    )
    message_count = models.IntegerField(default=0)

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interview_conversations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation {self.call_sid} - {self.candidate_id}"
