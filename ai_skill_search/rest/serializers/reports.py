from rest_framework import serializers

from ai_skill_search.models import CandidateSkillMatch


class CandidateSkillSearchReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateSkillMatch
        fields = "__all__"
