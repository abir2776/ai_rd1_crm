# interview/views/aiphonecallconfig.py
from django.db import transaction
from rest_framework import generics

from interview.models import AIPhoneCallConfig
from interview.rest.serializers.config import AIPhoneCallConfigSerializer


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
    lookup_field = "uid"

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        return AIPhoneCallConfig.objects.filter(
            organization=organization
        ).select_related("platform")

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
