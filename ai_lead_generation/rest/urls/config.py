from django.urls import path

from ai_lead_generation.rest.views.config import (
    LeadGenerationConfigListCreateView,
    MarketingAutomationConfigListCreateView,
)

urlpatterns = [
    path(
        "part1",
        LeadGenerationConfigListCreateView.as_view(),
        name="lead-generation-config",
    ),
    path(
        "part2",
        MarketingAutomationConfigListCreateView.as_view(),
        name="marketing-automation-config-list-create",
    ),
]
