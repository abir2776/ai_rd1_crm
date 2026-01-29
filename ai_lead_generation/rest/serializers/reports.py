from rest_framework import serializers

from ai_lead_generation.models import CandidateLeadResult, MarketingAutomationReport


class CandidateLeadResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateLeadResult
        fields = "__all__"


class OpportunitiesCreateReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingAutomationReport
        fields = "__all__"
