from django.db import models


class UserGender(models.TextChoices):
    FEMALE = "FEMALE", "Female"
    MALE = "MALE", "Male"
    UNKNOWN = "UNKNOWN", "Unknown"
    OTHER = "OTHER", "Other"


class TwilioPhoneNumberStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    RELEASED = "RELEASED", "Released"
    SUSPENDED = "SUSPENDED", "Suspended"


class TwilioPhoneNumberType(models.TextChoices):
    LOCAL = "LOCAL", "Local"
    TOLL_FREE = "TOLL_FREE", "Toll Free"
    MOBILE = "MOBILE", "Mobile"
    SHORT_CODE = "SHORT_CODE", "Short Code"
