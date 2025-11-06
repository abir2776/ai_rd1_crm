from django.urls import path

from ..views.conversations import GetConversationView, SaveConversationView

urlpatterns = [
    path("save/", SaveConversationView.as_view(), name="save_conversation"),
    path("<str:call_sid>/", GetConversationView.as_view(), name="get_conversation"),
]
