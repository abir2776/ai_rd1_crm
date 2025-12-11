from rest_framework import generics
from rest_framework.exceptions import ValidationError

from ai_gdpr.models import GDPREmailConfig
from ai_gdpr.rest.serializers.config import GDPREmailConfigSerializer


class GDPREmailConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = GDPREmailConfigSerializer

    def get_queryset(self):
        org = self.request.user.get_organization()
        return GDPREmailConfig.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = self.request.user.get_organization()
        if GDPREmailConfig.objects.filter(organization=org).exists():
            raise ValidationError(
                "A GDPR Email Config already exists for this organization."
            )

        serializer.save(organization=org)
