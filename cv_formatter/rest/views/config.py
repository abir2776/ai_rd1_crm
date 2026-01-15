from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

from cv_formatter.models import CVFormatterConfig
from cv_formatter.rest.serializers.config import CVformatterConfigSerializer


class CVFormatterConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = CVformatterConfigSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        queryset = CVFormatterConfig.objects.filter(organization=organization)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        organization = self.request.user.get_organization()
        if CVFormatterConfig.objects.filter(organization=organization).exists():
            raise ValidationError(
                {"detail": "CV formatter config already exists for your organization"}
            )

        serializer.save()


class CVFormatterConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CVformatterConfigSerializer

    def get_object(self):
        organization = self.request.user.get_organization()
        config = CVFormatterConfig.objects.filter(organization=organization).first()
        if not config:
            raise NotFound("No CV formatter config found for your organization")
        return config

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
