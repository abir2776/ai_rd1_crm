import uuid

import requests
from autoslug import AutoSlugField
from django.db import models
from django.utils import timezone
from versatileimagefield.fields import VersatileImageField

from common.choices import Status
from common.models import BaseModelWithUID
from core.models import User

from .choices import AuthTypeChoices, OrganizationInvitationStatus, OrganizationUserRole
from .utils import (
    get_organization_media_path_prefix,
    get_organization_slug,
    get_platform_media_path_prefix,
    get_platform_slug,
)


class Organization(BaseModelWithUID):
    name = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from=get_organization_slug, unique=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    logo = VersatileImageField(
        "Logo",
        upload_to=get_organization_media_path_prefix,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return self.name


class Platform(BaseModelWithUID):
    name = models.CharField(max_length=100, unique=True)
    slug = AutoSlugField(populate_from=get_platform_slug, unique=True)
    description = models.TextField(blank=True, null=True)
    base_url = models.URLField(blank=True, null=True)
    redirect_uri = models.URLField(blank=True, null=True)
    client_id = models.CharField(max_length=255, blank=True, null=True)
    client_secret = models.CharField(max_length=255, blank=True, null=True)
    scope = models.CharField(max_length=255, blank=True, null=True)
    response_type = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    auth_type = models.CharField(
        max_length=20,
        choices=AuthTypeChoices.choices,
        default=AuthTypeChoices.OAUTH2,
    )
    logo = VersatileImageField(
        "Logo",
        upload_to=get_platform_media_path_prefix,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Platform"
        verbose_name_plural = "Platforms"

    def __str__(self):
        return self.name


class OrganizationPlatform(BaseModelWithUID):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="platform_connections"
    )
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name="organization_connections"
    )
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_type = models.CharField(max_length=50, blank=True, null=True)
    base_url = models.URLField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    is_connected = models.BooleanField(default=False)
    connected_at = models.DateTimeField(blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        unique_together = ("organization", "platform")
        verbose_name = "Organization Platform Connection"
        verbose_name_plural = "Organization Platform Connections"

    def __str__(self):
        return f"{self.organization.name} - {self.platform.name}"

    def refresh_access_token(self):
        token_url = "https://id.jobadder.com/connect/token"
        client_id = self.platform.client_id
        client_secret = self.platform.client_secret

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        try:
            response = requests.post(token_url, data=data, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to refresh token: {e}")

        token_data = response.json()

        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        self.token_type = token_data.get("token_type", "Bearer")

        expires_in = token_data.get("expires_in")
        if expires_in:
            self.expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)

        self.is_connected = True
        self.connected_at = timezone.now()
        self.save(
            update_fields=[
                "access_token",
                "refresh_token",
                "token_type",
                "expires_at",
                "is_connected",
                "connected_at",
            ]
        )

        return self.access_token


class OrganizationUser(BaseModelWithUID):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="users"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="organization_profile"
    )
    role = models.CharField(
        max_length=20, choices=OrganizationUserRole, default="viewer"
    )
    title = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        unique_together = ("organization", "user")
        verbose_name = "Organization User"
        verbose_name_plural = "Organization Users"
        ordering = ["organization", "user__username"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.organization.name})"

    def activate(self):
        self.is_active = True
        self.save()

    def deactivate(self):
        self.is_active = False
        self.save()

    def update_last_active(self):
        self.last_active = timezone.now()
        self.save()


class OrganizationUserInvitation(BaseModelWithUID):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20, choices=OrganizationUserRole, default="viewer"
    )
    token = models.UUIDField(
        db_index=True, unique=True, default=uuid.uuid4, editable=False
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_invitations"
    )
    invitation_status = models.CharField(
        max_length=20,
        choices=OrganizationInvitationStatus.choices,
        default="pending",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Organization Invitation"
        verbose_name_plural = "Organization Invitations"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Invitation to {self.email} for {self.organization.name}"
