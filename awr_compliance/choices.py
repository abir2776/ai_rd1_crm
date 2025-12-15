from django.db import models


class Interval(models.TextChoices):
    SIX_MONTH = "6_MONTH", "6 Months"
    TWELVE_MONTH = "12_MONTH", "12 Months"
    TWENTY_FOUR_MONTH = "24_MONTH", "24 Months"
    THIRTY_SIX_MONTH = "36_MONTH", "36 Months"
    FORTY_EIGHT_MONTH = "48_MONTH", "48 Months"
