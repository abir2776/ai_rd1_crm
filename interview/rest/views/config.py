# interview/views/aiphonecallconfig.py
from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound

from interview.models import AIPhoneCallConfig, PrimaryQuestion
from interview.rest.serializers.config import (
    AIPhoneCallConfigSerializer,
    PrimaryQuestionSerializer,
)


class AIPhoneCallConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = AIPhoneCallConfigSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        return AIPhoneCallConfig.objects.filter(
            organization=organization
        ).select_related("platform")

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save()


class AIPhoneCallConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AIPhoneCallConfigSerializer

    def get_object(self):
        organization = self.request.user.get_organization()
        config = AIPhoneCallConfig.objects.filter(organization=organization).first()
        if not config:
            raise NotFound("No call config found for your organization")
        return config

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()


class PrimaryQuestionListView(generics.ListCreateAPIView):
    serializer_class = PrimaryQuestionSerializer
    queryset = PrimaryQuestion.objects.filter()
