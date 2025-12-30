from django.db import models


class FeatureType(models.TextChoices):
    AI_CALL = "AI_CALL", "AI Call"
    AI_SMS = "AI_SMS", "AI SMS"
    AI_WHATSAPP = "AI_WHATSAPP", "AI WhatsApp"

    AI_CV_FORMATTER = "AI_CV_FORMATTER", "AI CV Formatter"
    AI_CANDIDATE_SKILL_SEARCH = "AI_CANDIDATE_SKILL_SEARCH", "AI Candidate Skill Search"
    AWR_COMPLIANCE = "AWR_COMPLIANCE", "AWR Compliance"
    AI_GDPR = "AI_GDPR", "AI GDPR"
    AI_LEAD_GENERATION = "AI_LEAD_GENERATION", "AI Lead Generation"
    AI_DOCUMENT_VERIFY = "AI_DOCUMENT_VERIFY", "AI Document Verify"
    AI_BDM_SALES_ENGINE = "AI_BDM_SALES_ENGINE", "AI BDM Sales Engine"
