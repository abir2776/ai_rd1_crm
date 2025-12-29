from rest_framework import serializers

from interview.models import InterviewMessageConversation


class MessageInterviewReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewMessageConversation
        fields = "__all__"
