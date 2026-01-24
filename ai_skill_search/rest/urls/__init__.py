from django.urls import include, path

urlpatterns = [
    path("config/", include("ai_skill_search.rest.urls.config")),
    path("reports/", include("ai_skill_search.rest.urls.reports")),
    path("list/", include("ai_skill_search.rest.urls.list")),
]
