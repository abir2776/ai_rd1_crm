from django.db import models


class Status(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PLACEHOLDER = "PLACEHOLDER", "Placeholder"
    ACTIVE = "ACTIVE", "Active"
    HIDDEN = "HIDDEN", "Hidden"
    PAUSED = "PAUSED", "Paused"
    REMOVED = "REMOVED", "Removed"
