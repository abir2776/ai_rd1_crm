from django.db import models


class BundleStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
    IN_REVIEW = "IN_REVIEW", "In Review"
    TWILIO_APPROVED = "TWILIO_APPROVED", "Twilio Approved"
    TWILIO_REJECTED = "TWILIO_REJECTED", "Twilio Rejected"
    PROVISIONALLY_APPROVED = "PROVISIONALLY_APPROVED", "Provisionally Approved"


class AddressStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class PhoneNumberStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Compliance"
    IN_REVIEW = "IN_REVIEW", "In Review"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    RELEASED = "RELEASED", "Released"
