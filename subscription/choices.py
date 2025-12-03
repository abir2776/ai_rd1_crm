from django.db import models


class FeatureType(models.TextChoices):
    AI_CALL = "AI_CALL", "Ai_call"
    AI_SMS = "AI_SMS", "Ai_sms"
    AI_WHATSAPP = "AI_WHATSAPP", "Ai_whatsapp"
