from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

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

        serializer.save()


class GDPREmailConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GDPREmailConfigSerializer

    def get_object(self):
        organization = self.request.user.get_organization()
        config = GDPREmailConfig.objects.filter(organization=organization).first()
        if not config:
            raise NotFound("No GDPR email config found for your organization")
        return config

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
