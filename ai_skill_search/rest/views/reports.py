from rest_framework.generics import ListAPIView

from ai_skill_search.models import CandidateSkillMatch
from ai_skill_search.rest.serializers.reports import (
    CandidateSkillSearchReportSerializer,
)


class CandidateSkillMatchReportListView(ListAPIView):
    serializer_class = CandidateSkillSearchReportSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return CandidateSkillMatch.objects.filter(organization=organization)
