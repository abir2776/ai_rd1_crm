from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

from interview.models import AIMessageConfig
from interview.rest.serializers.messageconfig import (
    AIPMessageConfigSerializer,
)


class AIMessageConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = AIPMessageConfigSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        return AIMessageConfig.objects.filter(organization=organization).select_related(
            "platform"
        )

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save()


class AIMessageConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AIPMessageConfigSerializer

    def get_object(self):
        organization = self.request.user.get_organization()

        config_type = self.request.query_params.get("type")
        if not config_type:
            raise ValidationError({"type": "type query parameter is required"})

        config = AIMessageConfig.objects.filter(
            organization=organization, type=config_type
        ).first()

        if not config:
            raise NotFound("No message config found for this type")

        return config

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
