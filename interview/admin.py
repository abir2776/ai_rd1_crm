from django.contrib import admin

from .models import (
    AIMessageConfig,
    AIPhoneCallConfig,
    InterviewCallConversation,
    InterviewMessageConversation,
    InterviewTaken,
    PrimaryQuestion,
    QuestionConfigConnection,
    QuestionMessageConfigConnection,
)

admin.site.register(InterviewCallConversation)
admin.site.register(InterviewTaken)
admin.site.register(AIPhoneCallConfig)
admin.site.register(PrimaryQuestion)
admin.site.register(QuestionConfigConnection)
admin.site.register(AIMessageConfig)
admin.site.register(InterviewMessageConversation)
admin.site.register(QuestionMessageConfigConnection)
