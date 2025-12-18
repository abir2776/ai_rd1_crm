from django.contrib import admin

from ai_skill_search.models import (
    AISkillSearchConfig,
    CandidateSkillMatch,
    JobSkillCache,
)

admin.site.register(CandidateSkillMatch)
admin.site.register(JobSkillCache)
admin.site.register(AISkillSearchConfig)
