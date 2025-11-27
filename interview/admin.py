from django.contrib import admin

from .models import (
    AIPhoneCallConfig,
    InterviewCallConversation,
    InterviewTaken,
    PrimaryQuestion,
    QuestionConfigConnection,
    AIMessageConfig,
)

admin.site.register(InterviewCallConversation)
admin.site.register(InterviewTaken)
admin.site.register(AIPhoneCallConfig)
admin.site.register(PrimaryQuestion)
admin.site.register(QuestionConfigConnection)
admin.site.register(AIMessageConfig)
