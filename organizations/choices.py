from django.db import models


class AuthTypeChoices(models.TextChoices):
    API_KEY = "API_KEY", "API Key"
    OAUTH2 = "OAUTH2", "OAuth2"
    BASIC = "BASIC", "Basic Auth"
    OTHER = "OTHER", "Other"


class OrganizationUserRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    MANAGER = "MANAGER", "Manager"
    RECRUITER = "RECRUITER", "Recruiter"
    VIEWER = "VIEWER", "Viewer"


class OrganizationInvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"
