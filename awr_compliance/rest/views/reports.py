from rest_framework.generics import ListAPIView

from awr_compliance.models import AWRTracker
from awr_compliance.rest.serializers.reports import AWRReportSerializer


class AWRReportListView(ListAPIView):
    serializer_class = AWRReportSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return AWRTracker.objects.filter(config__organization=organization)
