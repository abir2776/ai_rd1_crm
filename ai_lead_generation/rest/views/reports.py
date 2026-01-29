from rest_framework.generics import ListAPIView

from ai_lead_generation.models import CandidateLeadResult, MarketingAutomationReport
from ai_lead_generation.rest.serializers.reports import (
    OpportunitiesCreateReportSerializer,
)


class CandidateLeadReportListView(ListAPIView):
    serializer_class = CandidateLeadResult
    queryset = CandidateLeadResult.objects.filter()


class OpportunitiesReportListView(ListAPIView):
    serializer_class = OpportunitiesCreateReportSerializer
    queryset = MarketingAutomationReport.objects.filter()
