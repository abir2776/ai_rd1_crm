# choices.py
from django.db import models


class BundleStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
    IN_REVIEW = "IN_REVIEW", "In Review"
    TWILIO_APPROVED = "TWILIO_APPROVED", "Twilio Approved"
    TWILIO_REJECTED = "TWILIO_REJECTED", "Twilio Rejected"


class AddressStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    FAILED = "FAILED", "Failed"


class PhoneNumberStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    RELEASED = "RELEASED", "Released"
    SUSPENDED = "SUSPENDED", "Suspended"


class EndUserType(models.TextChoices):
    """End user type for regulatory compliance"""

    INDIVIDUAL = "individual", "Individual"
    BUSINESS = "business", "Business"
