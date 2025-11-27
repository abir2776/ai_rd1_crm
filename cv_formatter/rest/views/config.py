from rest_framework.generics import ListCreateAPIView

from cv_formatter.models import CVFormatterConfig
from cv_formatter.rest.serializers.config import CVformatterConfigSerializer


class CVFormatterConfigListCreateView(ListCreateAPIView):
    serializer_class = CVformatterConfigSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        queryset = CVFormatterConfig.objects.filter(organization=organization)
        return queryset
