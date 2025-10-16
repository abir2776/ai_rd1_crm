import logging
from django.db import transaction

from rest_framework import serializers
from versatileimagefield.serializers import VersatileImageFieldSerializer

from core.models import User
from organizations.models import Organization, OrganizationUser
from organizations.choices import OrganizationUserRole
from common.tasks import send_email_task

logger = logging.getLogger(__name__)


class PublicOrganizationRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=50)
    phone = serializers.CharField(min_length=7, max_length=20)
    first_name = serializers.CharField(min_length=2, max_length=50)
    last_name = serializers.CharField(min_length=2, max_length=50)
    org_name = serializers.CharField(min_length=2, max_length=100)
    org_website = serializers.URLField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True)
    country = serializers.CharField(required=False, allow_null=True)
    org_description = serializers.CharField(required=False, allow_null=True)
    logo = VersatileImageFieldSerializer(
        sizes=[
            ("original", "url"),
            ("at256", "crop__256x256"),
            ("at512", "crop__512x512"),
        ],
        required=False,
    )

    def validate_email(self, data):
        email = data.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with email already exists!")
        return data

    def validate_phone(self, data):
        phone = data
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("User with phone already exists!")
        return data

    def create(self, validated_data, *args, **kwargs):
        with transaction.atomic():
            email = validated_data["email"].lower()
            password = validated_data["password"]
            phone = validated_data["phone"]
            first_name = validated_data["first_name"]
            last_name = validated_data["last_name"]

            user = User.objects.create(
                email=email,
                username=email,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            user.set_password(password)
            user.save()
            logger.debug(f"Created new user: {user}")

            org_name = validated_data["org_name"]
            org_website = validated_data.get("org_website", None)
            address = validated_data.get("address", None)
            country = validated_data.get("country", None)
            org_description = validated_data.get("org_description", None)
            logo = validated_data.get("logo", None)
            organization = Organization.objects.create(
                name=org_name,
                email=email,
                phone=phone,
                website=org_website,
                address=address,
                country=country,
                description=org_description,
                logo=logo,
            )
            logger.debug(f"Created new user: {user}")
            OrganizationUser.objects.create(
                user=user,
                organization=organization,
                role=OrganizationUserRole.OWNER,
                phone=phone,
                is_active=True,
            )
            logger.debug(f"Added user: {user} to organization: {organization}")
            context = {
                "username": user.get_full_name(),
                "verification_link": f"http://example.com/verify",
                "current_year": 2025,
            }
            send_email_task.delay(
                subject="Verify your email address",
                recipient=email,
                template_name="organization_register/verify.html",
                context=context,
            )
        return user
