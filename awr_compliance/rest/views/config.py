from rest_framework import generics
from rest_framework.exceptions import ValidationError

from awr_compliance.models import AWRConfig
from awr_compliance.rest.serializers.config import AWRConfigSerializer


class AWRConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = AWRConfigSerializer

    def get_queryset(self):
        org = self.request.user.get_organization()
        return AWRConfig.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = self.request.user.get_organization()
        if AWRConfig.objects.filter(organization=org).exists():
            raise ValidationError(
                "A GDPR Email Config already exists for this organization."
            )

        serializer.save()
