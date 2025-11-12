from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from interview.models import InterviewConversation

from ..serializers.conversations import (
    ConversationSaveSerializer,
    InterviewConversationSerializer,
)


class SaveConversationView(APIView):
    """
    API endpoint to save interview conversation
    POST /api/interview/conversation/save/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConversationSaveSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"error": "Invalid data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data

        try:
            # Create or update conversation record
            conversation, created = InterviewConversation.objects.update_or_create(
                call_sid=validated_data["call_sid"],
                defaults={
                    "application_id": validated_data["application_id"],
                    "organization_id": validated_data["organization_id"],
                    "interview_id": validated_data["interview_id"],
                    "candidate_id": validated_data["candidate_id"],
                    "job_id": validated_data["job_id"],
                    "conversation_text": validated_data["conversation_text"],
                    "conversation_json": validated_data["conversation_json"],
                    "message_count": validated_data["message_count"],
                    "started_at": validated_data["started_at"],
                    "ended_at": validated_data["ended_at"],
                },
            )

            response_serializer = InterviewConversationSerializer(conversation)

            return Response(
                {
                    "success": True,
                    "message": "Conversation saved successfully"
                    if created
                    else "Conversation updated successfully",
                    "created": created,
                    "data": response_serializer.data,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Failed to save conversation", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetConversationView(APIView):
    """
    API endpoint to retrieve conversation
    GET /api/interview/conversation/<call_sid>/
    """

    def get(self, request, call_sid):
        try:
            organization = request.user.get_organization()
            conversation = InterviewConversation.objects.get(
                call_sid=call_sid, organization=organization
            )
            serializer = InterviewConversationSerializer(conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except InterviewConversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
