from django.db import transaction
from rest_framework import generics

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
    lookup_field = "uid"

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        return AIMessageConfig.objects.filter(organization=organization).select_related(
            "platform"
        )

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
