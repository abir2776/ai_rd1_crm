import os
from dotenv import load_dotenv
from openai import OpenAI
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AIRecruiterChatView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            messages = request.data.get("messages", [])

            if not messages or not isinstance(messages, list):
                return Response(
                    {"error": "messages must be a list of message objects"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            system_instruction = (
                "You are RecruiterAI — a professional assistant for a recruitment automation platform. "
                "You understand and explain tools like AI WhatsApp Recruiter, AI Phone Call Recruiter, "
                "AI CV Formatter, AI GDPR Compliance, and AWR Compliance. "
                "You always respond clearly, concisely, and professionally, staying focused on recruitment automation. "
                "Never make up new features. Continue conversations naturally using context from prior messages."
            )
            conversation = client.conversations.create(
                model="gpt-4o", instructions=system_instruction, messages=messages
            )
            ai_message = None
            if conversation and conversation.output and len(conversation.output) > 0:
                ai_message = conversation.output[0].content[0].text

            return Response(
                {"reply": ai_message or "No response generated."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
