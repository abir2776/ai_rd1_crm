from rest_framework.generics import ListAPIView

from ai_gdpr.models import GDPREmailTracker
from ai_gdpr.rest.serializers.reports import GDPRReportSerializer


class GDPRReportListView(ListAPIView):
    serializer_class = GDPRReportSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return GDPREmailTracker.objects.filter(organization=organization)
