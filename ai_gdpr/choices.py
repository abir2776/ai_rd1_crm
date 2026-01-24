from django.db import models


class ProgressStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    IN_PROGRESS = "IN_PROGRESS", "In_progress"
    COMPLETED = "COMPLETED", "Completed"


class Interval(models.TextChoices):
    SIX_MONTH = "6_MONTH", "6 Months"
    TWELVE_MONTH = "12_MONTH", "12 Months"
    TWENTY_FOUR_MONTH = "24_MONTH", "24 Months"
    THIRTY_SIX_MONTH = "36_MONTH", "36 Months"
    FORTY_EIGHT_MONTH = "48_MONTH", "48 Months"
