import logging
import uuid

from autoslug import AutoSlugField
from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from versatileimagefield.fields import VersatileImageField

from common.choices import Status
from common.models import BaseModelWithUID

from .choices import TwilioPhoneNumberStatus, TwilioPhoneNumberType, UserGender
from .managers import CustomUserManager
from .utils import get_user_media_path_prefix, get_user_slug

logger = logging.getLogger(__name__)


class User(AbstractUser, BaseModelWithUID):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, null=True, blank=True)
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
    token = models.UUIDField(
        db_index=True, unique=True, default=uuid.uuid4, editable=False
    )
    is_verified = models.BooleanField(default=False)

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


class TwilioPhoneNumber(BaseModelWithUID):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="twilio_phone_numbers",
        help_text="Organization who owns this phone number",
    )
    twilio_sid = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Twilio Phone Number SID",
    )
    phone_number = PhoneNumberField(
        unique=True,
        db_index=True,
        help_text="The purchased phone number in E.164 format",
    )
    friendly_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Friendly name for the phone number",
    )
    country_code = models.CharField(
        max_length=2,
        help_text="ISO country code (e.g., US, CA, GB)",
    )
    area_code = models.CharField(
        max_length=10,
        blank=True,
        help_text="Area code of the phone number",
    )
    locality = models.CharField(
        max_length=255,
        blank=True,
        help_text="City or locality of the phone number",
    )
    region = models.CharField(
        max_length=255,
        blank=True,
        help_text="State or region of the phone number",
    )
    number_type = models.CharField(
        max_length=20,
        choices=TwilioPhoneNumberType.choices,
        default=TwilioPhoneNumberType.LOCAL,
    )

    status = models.CharField(
        max_length=20,
        choices=TwilioPhoneNumberStatus.choices,
        default=TwilioPhoneNumberStatus.ACTIVE,
    )
    voice_capable = models.BooleanField(
        default=True,
        help_text="Can make/receive voice calls",
    )
    sms_capable = models.BooleanField(
        default=True,
        help_text="Can send/receive SMS messages",
    )
    mms_capable = models.BooleanField(
        default=False,
        help_text="Can send/receive MMS messages",
    )
    fax_capable = models.BooleanField(
        default=False,
        help_text="Can send/receive faxes",
    )
    voice_url = models.URLField(
        blank=True,
        help_text="URL for handling incoming voice calls",
    )
    voice_method = models.CharField(
        max_length=10,
        choices=[("GET", "GET"), ("POST", "POST")],
        default="POST",
        blank=True,
    )
    sms_url = models.URLField(
        blank=True,
        help_text="URL for handling incoming SMS messages",
    )
    sms_method = models.CharField(
        max_length=10,
        choices=[("GET", "GET"), ("POST", "POST")],
        default="POST",
        blank=True,
    )
    status_callback_url = models.URLField(
        blank=True,
        help_text="URL for status callbacks",
    )
    monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Monthly cost in USD",
    )
    release_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when the number was released",
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this phone number",
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the user's primary phone number",
    )

    twilio_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata from Twilio API",
    )

    class Meta:
        verbose_name = "Twilio Phone Number"
        verbose_name_plural = "Twilio Phone Numbers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["twilio_sid"]),
        ]

    def __str__(self):
        return f"TwilioPhoneNumber(UID: {self.uid}, Phone: {self.phone_number}, Status: {self.status})"
