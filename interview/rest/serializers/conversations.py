from rest_framework import serializers
from interview.models import InterviewConversation


class ConversationSaveSerializer(serializers.Serializer):
    call_sid = serializers.CharField(max_length=100)
    application_id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    candidate_id = serializers.IntegerField()
    job_id = serializers.IntegerField()
    company_id = serializers.IntegerField()
    conversation_text = serializers.CharField()
    conversation_json = serializers.JSONField()
    message_count = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField()


class InterviewConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewConversation
        fields = "__all__"
