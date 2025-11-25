from django.db import models


class InterviewType(models.TextChoices):
    AI_CALL = "AI_CALL", "Ai_call"
    AI_SMS = "AI_SMS", "Ai_sms"
    AI_WHATSAPP = "AI_WHATSAPP", "Ai_whatsapp"


class ProgressStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    IN_PROGRESS = "IN_PROGRESS", "In_progress"
    COMPLETED = "COMPLETED", "Completed"
