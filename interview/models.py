from django.db import models
from common.choices import Status
from common.models import BaseModelWithUID


class InterviewType(BaseModelWithUID):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.ACTIVE
    )

    def __str__(self):
        return self.name


class InterviewTaken(BaseModelWithUID):
    company_id = models.PositiveIntegerField()
    application_id = models.PositiveIntegerField()
    interview_type = models.ForeignKey(InterviewType, on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField()

    def __str__(self):
        return f"company_id: {self.company_id} - application_id: {self.application_id} - interview_type: {self.interview_type.name}"
