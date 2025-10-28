# models.py
import logging

from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from common.choices import Status
from common.models import BaseModelWithUID

from .choices import AddressStatus, BundleStatus, PhoneNumberStatus, EndUserType

logger = logging.getLogger(__name__)


class TwilioSubAccount(BaseModelWithUID):
    """
    Twilio Subaccount for each customer
    """

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="twilio_subaccount",
        help_text="Customer who owns this subaccount",
    )

    twilio_account_sid = models.CharField(
        max_length=34,
        unique=True,
        db_index=True,
        help_text="Twilio Subaccount SID (starts with AC)",
    )

    twilio_auth_token = models.CharField(
        max_length=255,
        help_text="Twilio Auth Token for this subaccount",
    )

    friendly_name = models.CharField(
        max_length=255,
        help_text="Friendly name for the subaccount",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        verbose_name = "Twilio Subaccount"
        verbose_name_plural = "Twilio Subaccounts"
        db_table = "twilio_subaccounts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.friendly_name} ({self.twilio_account_sid})"


class EndUser(BaseModelWithUID):
    """
    End User information for regulatory compliance
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="end_users",
    )

    subaccount = models.ForeignKey(
        TwilioSubAccount,
        on_delete=models.CASCADE,
        related_name="end_users",
    )

    end_user_sid = models.CharField(
        max_length=34,
        unique=True,
        db_index=True,
        help_text="Twilio End User SID (starts with IT)",
    )

    friendly_name = models.CharField(
        max_length=255,
        help_text="Friendly name for the end user",
    )

    end_user_type = models.CharField(
        max_length=20,
        choices=EndUserType.choices,
    )

    # Business Information (required for business type)
    business_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Legal business name",
    )

    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Business registration/tax ID number",
    )

    business_registration_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Registration authority (e.g., EIN, VAT, ABN)",
    )

    business_website = models.URLField(
        blank=True,
        help_text="Business website URL",
    )

    business_identity = models.CharField(
        max_length=50,
        blank=True,
        help_text="Business classification/industry",
    )

    # Authorized Representative Information
    first_name = models.CharField(
        max_length=100,
        help_text="First name of authorized representative",
    )

    last_name = models.CharField(
        max_length=100,
        help_text="Last name of authorized representative",
    )

    email = models.EmailField(
        help_text="Email of authorized representative",
    )

    phone_number = PhoneNumberField(
        help_text="Phone number of authorized representative",
    )

    # Additional Information
    is_subassigned = models.BooleanField(
        default=False,
        help_text="Whether number is assigned to end customer",
    )

    comments = models.TextField(
        blank=True,
        help_text="Optional comments",
    )

    status = models.CharField(
        max_length=20,
        default="active",
    )

    twilio_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "End User"
        verbose_name_plural = "End Users"
        db_table = "end_users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.friendly_name} - {self.end_user_type}"


class RegulatoryBundle(BaseModelWithUID):
    """
    Regulatory Bundle (identity verification) for phone number compliance
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="regulatory_bundles",
    )

    subaccount = models.ForeignKey(
        TwilioSubAccount,
        on_delete=models.CASCADE,
        related_name="bundles",
    )

    end_user = models.ForeignKey(
        EndUser,
        on_delete=models.CASCADE,
        related_name="bundles",
        null=True,
        blank=True,
        help_text="Associated end user information",
    )

    bundle_sid = models.CharField(
        max_length=34,
        unique=True,
        db_index=True,
        help_text="Twilio Bundle SID (starts with BU)",
    )

    friendly_name = models.CharField(
        max_length=255,
        help_text="Friendly name for the bundle",
    )

    status = models.CharField(
        max_length=30,
        choices=BundleStatus.choices,
        default=BundleStatus.DRAFT,
    )

    # Bundle details
    iso_country = models.CharField(
        max_length=2,
        help_text="2-digit ISO country code (e.g., US, DE, AU)",
    )

    number_type = models.CharField(
        max_length=20,
        help_text="Phone number type: local, mobile, national, toll-free",
    )

    end_user_type = models.CharField(
        max_length=20,
        help_text="End user type: individual or business",
    )

    regulation_sid = models.CharField(
        max_length=34,
        blank=True,
        help_text="Twilio Regulation SID (starts with RN)",
    )

    # Notification settings
    email = models.EmailField(
        help_text="Email to receive bundle status updates",
    )

    status_callback_url = models.URLField(
        blank=True,
        help_text="Webhook URL for status updates",
    )

    # Metadata
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection if bundle is rejected",
    )

    twilio_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata from Twilio",
    )

    class Meta:
        verbose_name = "Regulatory Bundle"
        verbose_name_plural = "Regulatory Bundles"
        db_table = "regulatory_bundles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "status"]),
            models.Index(fields=["bundle_sid"]),
        ]

    def __str__(self):
        return f"{self.friendly_name} - {self.status}"


class RegulatoryAddress(BaseModelWithUID):
    """
    Address for regulatory compliance
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="regulatory_addresses",
    )

    subaccount = models.ForeignKey(
        TwilioSubAccount,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    address_sid = models.CharField(
        max_length=34,
        unique=True,
        db_index=True,
        help_text="Twilio Address SID (starts with AD)",
    )

    friendly_name = models.CharField(
        max_length=255,
        help_text="Friendly name for the address",
    )

    # Address fields
    customer_name = models.CharField(
        max_length=255,
        help_text="Name of the customer/business",
    )

    street = models.CharField(
        max_length=255,
        help_text="Street address",
    )

    street_secondary = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secondary street address (e.g., Apt, Suite)",
    )

    city = models.CharField(
        max_length=100,
        help_text="City",
    )

    region = models.CharField(
        max_length=100,
        help_text="State/Province/Region",
    )

    postal_code = models.CharField(
        max_length=20,
        help_text="Postal/ZIP code",
    )

    iso_country = models.CharField(
        max_length=2,
        help_text="2-digit ISO country code",
    )

    status = models.CharField(
        max_length=20,
        choices=AddressStatus.choices,
        default=AddressStatus.PENDING,
    )

    # Emergency services flag
    emergency_enabled = models.BooleanField(
        default=False,
        help_text="Whether this address is enabled for emergency services",
    )

    # Metadata
    twilio_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = "Regulatory Address"
        verbose_name_plural = "Regulatory Addresses"
        db_table = "regulatory_addresses"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "status"]),
            models.Index(fields=["address_sid"]),
        ]

    def __str__(self):
        return f"{self.customer_name} - {self.city}, {self.region}"


class TwilioPhoneNumber(BaseModelWithUID):
    """
    Twilio phone number with compliance requirements
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="twilio_phone_numbers",
    )

    subaccount = models.ForeignKey(
        TwilioSubAccount,
        on_delete=models.CASCADE,
        related_name="phone_numbers",
    )

    bundle = models.ForeignKey(
        RegulatoryBundle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phone_numbers",
        help_text="Associated regulatory bundle",
    )

    address = models.ForeignKey(
        RegulatoryAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phone_numbers",
        help_text="Associated address",
    )

    # Twilio fields
    twilio_sid = models.CharField(
        max_length=34,
        unique=True,
        db_index=True,
        help_text="Twilio Phone Number SID (starts with PN)",
    )

    phone_number = PhoneNumberField(
        unique=True,
        db_index=True,
        help_text="Phone number in E.164 format",
    )

    friendly_name = models.CharField(
        max_length=255,
        blank=True,
    )

    # Number details
    country_code = models.CharField(max_length=2)
    area_code = models.CharField(max_length=10, blank=True)
    locality = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=255, blank=True)
    number_type = models.CharField(
        max_length=20,
        help_text="local, mobile, national, toll-free",
    )

    # Capabilities
    voice_capable = models.BooleanField(default=True)
    sms_capable = models.BooleanField(default=True)
    mms_capable = models.BooleanField(default=False)
    fax_capable = models.BooleanField(default=False)

    # Status and compliance
    status = models.CharField(
        max_length=20,
        choices=PhoneNumberStatus.choices,
        default=PhoneNumberStatus.PENDING,
    )

    compliance_status = models.CharField(
        max_length=30,
        default="pending",
        help_text="Compliance verification status",
    )

    # Configuration
    voice_url = models.URLField(blank=True)
    sms_url = models.URLField(blank=True)

    # Pricing
    monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )

    purchase_date = models.DateTimeField(auto_now_add=True)
    release_date = models.DateTimeField(null=True, blank=True)

    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    twilio_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Twilio Phone Number"
        verbose_name_plural = "Twilio Phone Numbers"
        db_table = "twilio_phone_numbers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "status"]),
            models.Index(fields=["subaccount_id", "status"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["twilio_sid"]),
        ]

    def __str__(self):
        return f"{self.phone_number}"


class SupportingDocument(BaseModelWithUID):
    """
    Supporting documents for regulatory compliance
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="supporting_documents",
    )

    bundle = models.ForeignKey(
        RegulatoryBundle,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    document_sid = models.CharField(
        max_length=34,
        unique=True,
        help_text="Twilio Supporting Document SID (starts with RD)",
    )

    document_type = models.CharField(
        max_length=50,
        help_text="Type of document (e.g., passport, business_license)",
    )

    friendly_name = models.CharField(max_length=255)

    # Document file
    file = models.FileField(
        upload_to="regulatory_documents/%Y/%m/",
        help_text="Uploaded document file",
        blank=True,
    )

    mime_type = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=20,
        default="pending",
    )

    twilio_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Supporting Document"
        verbose_name_plural = "Supporting Documents"
        db_table = "supporting_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.document_type} - {self.friendly_name}"
