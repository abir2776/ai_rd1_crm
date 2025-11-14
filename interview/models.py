from django.db import models

from common.choices import Status
from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform
from phone_number.models import TwilioPhoneNumber


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
    application_id = models.PositiveIntegerField()
    candidate_id = models.PositiveIntegerField()
    job_id = models.PositiveIntegerField()
    interview_status = models.CharField(max_length=100, null=True, blank=True)
    ai_dicision = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    call_sid = models.CharField(max_length=100)
    call_duration = models.CharField(max_length=100)
    call_status = models.CharField(max_length=100)
    disconnection_reason = models.CharField(max_length=100)

    def __str__(self):
        return (
            f"candidate_id: {self.candidate_id} - application_id: {self.application_id}"
        )


class InterviewConversation(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    interview = models.ForeignKey(InterviewTaken, on_delete=models.CASCADE)
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


class PrimaryQuestion(BaseModelWithUID):
    question = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.ACTIVE
    )

    def __str__(self):
        return self.status


class AIPhoneCallConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    phone = models.ForeignKey(TwilioPhoneNumber, on_delete=models.CASCADE)
    end_call_if_primary_answer_negative = models.BooleanField(default=False)
    application_status_for_calling = models.PositiveIntegerField()
    jobad_status_for_calling = models.CharField(max_length=255)
    calling_time_after_status_update = models.DurationField()
    status_for_unsuccessful_call = models.PositiveIntegerField()
    status_for_successful_call = models.PositiveIntegerField()
    status_when_call_is_placed = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.organization.name}-{self.platform.platform.name}"

    def get_primary_questions(self):
        connections = QuestionConfigConnection.objects.filter(
            config=self
        ).select_related("question")
        return [conn.question.question for conn in connections]


class QuestionConfigConnection(BaseModelWithUID):
    question = models.ForeignKey(PrimaryQuestion, on_delete=models.CASCADE)
    config = models.ForeignKey(AIPhoneCallConfig, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.question.question}-{self.config.organization}"
