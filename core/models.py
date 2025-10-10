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
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = PhoneNumberField(unique=True, db_index=True, verbose_name="Phone Number")
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
