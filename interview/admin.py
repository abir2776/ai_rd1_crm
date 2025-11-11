from django.contrib import admin

from .models import (
    AIPhoneCallConfig,
    InterviewConversation,
    InterviewTaken,
    PrimaryQuestion,
    QuestionConfigConnection,
)

admin.site.register(InterviewConversation)
admin.site.register(InterviewTaken)
admin.site.register(AIPhoneCallConfig)
admin.site.register(PrimaryQuestion)
admin.site.register(QuestionConfigConnection)
