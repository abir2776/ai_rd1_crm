from rest_framework import generics
from rest_framework.exceptions import ValidationError

from ai_skill_search.models import AISkillSearchConfig
from ai_skill_search.rest.serializers.config import SkillSearchConfigSerializer


class SkillSearchConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = SkillSearchConfigSerializer

    def get_queryset(self):
        org = self.request.user.get_organization()
        return AISkillSearchConfig.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = self.request.user.get_organization()
        if AISkillSearchConfig.objects.filter(organization=org).exists():
            raise ValidationError(
                "A Skill Search Config already exists for this organization."
            )

        serializer.save()
