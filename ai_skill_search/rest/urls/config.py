from django.urls import path

from ai_skill_search.rest.views.config import SkillSearchConfigListCreateView

urlpatterns = [
    path("", SkillSearchConfigListCreateView.as_view(), name="skill-search-config"),
]
