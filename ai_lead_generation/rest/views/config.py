from rest_framework import generics
from rest_framework.exceptions import ValidationError

from ai_lead_generation.models import LeadGenerationConfig, MarketingAutomationConfig
from ai_lead_generation.rest.serializers.config import (
    LeadGenerationConfigSerializer,
    MarketingAutomationConfigSerializer,
)
from organizations.models import OrganizationPlatform


class LeadGenerationConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = LeadGenerationConfigSerializer

    def get_queryset(self):
        org = self.request.user.get_organization()
        return LeadGenerationConfig.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = self.request.user.get_organization()
        if LeadGenerationConfig.objects.filter(organization=org).exists():
            raise ValidationError(
                "A Skill Search Config already exists for this organization."
            )

        serializer.save()


class MarketingAutomationConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = MarketingAutomationConfigSerializer

    def get_queryset(self):
        org = self.request.user.get_organization()
        return MarketingAutomationConfig.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = self.request.user.get_organization()
        platform_uid = serializer.validated_data.get("platform_uid")

        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        if (
            platform
            and MarketingAutomationConfig.objects.filter(
                organization=org, platform=platform
            ).exists()
        ):
            raise ValidationError(
                "A Marketing Automation Config already exists for this organization and platform."
            )

        serializer.save()
