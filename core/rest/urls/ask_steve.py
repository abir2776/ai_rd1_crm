from django.urls import path

from ..views.ask_steve import AIRecruiterChatView

urlpatterns = [
    path("", AIRecruiterChatView.as_view(), name="steve-chat-bot"),
]
