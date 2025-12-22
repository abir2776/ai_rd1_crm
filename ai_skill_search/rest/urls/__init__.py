from django.urls import include, path

urlpatterns = [
    path("config/", include("ai_skill_search.rest.urls.config")),
]
