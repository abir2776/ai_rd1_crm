from django.db import models

from common.choices import Status
from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform
from phone_number.models import TwilioPhoneNumber

from .choices import InterviewType, ProgressStatus


class InterviewTaken(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    application_id = models.PositiveIntegerField(null=True, blank=True)
    candidate_id = models.PositiveIntegerField(null=True, blank=True)
    job_id = models.PositiveIntegerField(null=True, blank=True)
    interview_status = models.CharField(max_length=100, null=True, blank=True)
    ai_decision = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    call_sid = models.CharField(max_length=100, null=True, blank=True)
    call_duration = models.CharField(max_length=100, null=True, blank=True)
    call_status = models.CharField(max_length=100, null=True, blank=True)
    disconnection_reason = models.CharField(max_length=100, null=True, blank=True)
    type = models.CharField(
        max_length=20,
        choices=InterviewType.choices,
        default=InterviewType.AI_CALL,
    )
    status = models.CharField(
        max_length=20,
        choices=ProgressStatus.choices,
        default=ProgressStatus.COMPLETED,
    )

    def __str__(self):
        return (
            f"candidate_id: {self.candidate_id} - application_id: {self.application_id}"
        )


class InterviewCallConversation(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    interview = models.ForeignKey(InterviewTaken, on_delete=models.CASCADE)
    call_sid = models.CharField(max_length=100, unique=True)
    application_id = models.PositiveIntegerField()
    candidate_id = models.PositiveIntegerField()
    candidate_name = models.CharField(max_length=100, null=True, blank=True)
    candidate_email = models.CharField(max_length=100, null=True, blank=True)
    candidate_phone = models.CharField(max_length=100, null=True, blank=True)
    job_id = models.PositiveIntegerField()

    conversation_text = models.TextField(help_text="Full conversation in text format")
    conversation_json = models.JSONField(
        help_text="Conversation messages in JSON format"
    )
    message_count = models.IntegerField(default=0)

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()

    class Meta:
        db_table = "interview_conversations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation {self.call_sid} - {self.candidate_id}"


class PrimaryQuestion(BaseModelWithUID):
    question = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.HIDDEN
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
    calling_time_after_status_update = models.IntegerField()
    status_for_unsuccessful_call = models.PositiveIntegerField()
    status_for_successful_call = models.PositiveIntegerField()
    status_when_call_is_placed = models.PositiveIntegerField(default=0)
    voice_id = models.CharField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "platform")

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

    class Meta:
        unique_together = ("question", "config")

    def __str__(self):
        return f"{self.question.question}-{self.config.organization}"


class AIMessageConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    phone = models.ForeignKey(TwilioPhoneNumber, on_delete=models.CASCADE)
    application_status_for_sms = models.PositiveIntegerField()
    jobad_status_for_sms = models.CharField(max_length=255, default="Current")
    sms_time_after_status_update = models.IntegerField()
    status_for_unsuccessful_sms = models.PositiveIntegerField()
    status_for_successful_sms = models.PositiveIntegerField()
    status_when_sms_is_send = models.PositiveIntegerField(default=0)
    twilio_sid = models.CharField(null=True, blank=True)
    twilio_auth_token = models.CharField(null=True, blank=True)
    whatsapp_template_sid = models.CharField(null=True, blank=True)
    type = models.CharField(
        max_length=20,
        choices=InterviewType.choices,
        default=InterviewType.AI_SMS,
    )

    class Meta:
        unique_together = ("organization", "platform", "phone")

    def __str__(self):
        return f"{self.organization.name}-{self.platform.platform.name}"


class QuestionMessageConfigConnection(BaseModelWithUID):
    question = models.ForeignKey(PrimaryQuestion, on_delete=models.CASCADE)
    config = models.ForeignKey(AIMessageConfig, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("question", "config")

    def __str__(self):
        return f"{self.question.question}-{self.config.organization}"


class InterviewMessageConversation(BaseModelWithUID):
    candidate_phone = models.CharField(max_length=255)
    candidate_name = models.CharField(max_length=255, null=True, blank=True)
    candidate_email = models.CharField(max_length=255, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    application_id = models.PositiveIntegerField()
    candidate_id = models.PositiveIntegerField()
    jobad_id = models.PositiveIntegerField()
    ai_instruction = models.TextField()
    conversation_json = models.JSONField(
        help_text="Conversation messages in JSON format"
    )
    message_count = models.IntegerField(default=0)
    type = type = models.CharField(
        max_length=20,
        choices=InterviewType.choices,
        default=InterviewType.AI_SMS,
    )
    status = models.CharField(
        max_length=20,
        choices=ProgressStatus.choices,
        default=ProgressStatus.INITIATED,
    )
    ai_dicision = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Conversation {self.application_id} - {self.candidate_id}"
