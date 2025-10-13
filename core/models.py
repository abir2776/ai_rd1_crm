import logging

from autoslug import AutoSlugField

from django.contrib.auth.models import AbstractUser
from django.db import models

from common.models import BaseModelWithUID

from phonenumber_field.modelfields import PhoneNumberField

from versatileimagefield.fields import VersatileImageField

from .choices import UserGender
from .managers import CustomUserManager
from common.choices import Status
from .utils import get_user_media_path_prefix, get_user_slug

logger = logging.getLogger(__name__)


class User(AbstractUser, BaseModelWithUID):
    email = models.EmailField(unique=True)
    phone = PhoneNumberField(
        unique=True, db_index=True, verbose_name="Phone Number", blank=True, null=True
    )
    slug = AutoSlugField(populate_from=get_user_slug, unique=True)
    avatar = VersatileImageField(
        "Avatar",
        upload_to=get_user_media_path_prefix,
        blank=True,
    )
    image = VersatileImageField(
        "Image",
        upload_to=get_user_media_path_prefix,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    gender = models.CharField(
        max_length=20,
        blank=True,
        choices=UserGender.choices,
        default=UserGender.UNKNOWN,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    height = models.FloatField(blank=True, null=True)
    weight = models.IntegerField(blank=True, null=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ("-date_joined",)

    def __str__(self):
        return f"UID: {self.uid}, Phone: {self.phone}"

    def get_name(self):
        name = " ".join([self.first_name, self.last_name])
        return name.strip()

    def get_organization(self):
        return (
            self.organization_profile.filter(is_active=True)
            .select_related("organization")
            .first()
            .organization
        )

    def get_role(self):
        return (
            self.organization_profile.filter(is_active=True)
            .select_related("organization")
            .first()
            .role
        )


class UserOTP(BaseModelWithUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_otps")
    otp = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.email} - {'Used' if self.is_used else 'Unused'}"

    def is_valid(self):
        from django.utils import timezone
        from datetime import timedelta

        return not self.is_used and (timezone.now() - self.created_at) < timedelta(
            minutes=2
        )
