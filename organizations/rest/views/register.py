import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.tasks import send_email_task
from core.models import User

from ..serializers import register


class PublicOrganizationRegistration(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        serializer = register.PublicOrganizationRegistrationSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(True, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserVerificationAPIView(APIView):
    permission_classes = [AllowAny]

    def put(self, request, token):
        data = request.data
        password = data.get("password", "")
        if len(password) == 0:
            return Response(
                {"detail": "You must give a password"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(token=token, is_verified=False).first()
        if user == None:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(password)
        user.is_verified = True
        user.save()
        return Response({"detail": "User Verified"}, status=status.HTTP_200_OK)


class UserForgetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = data.get("email", "")
        if len(email) == 0:
            return Response(
                {"detail": "You must give a email"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(email=email).first()
        if user == None:
            return Response(
                {"detail": "There is not any active with this given email"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.token = uuid.uuid4()
        user.is_verified = False
        user.save()
        context = {
            "username": user.get_full_name(),
            "verification_link": f"{settings.FRONTEND_BASE_URL}/resetPassword/{user.token}?email={email}",
            "current_year": 2025,
        }
        send_email_task.delay(
            subject="Reset your password",
            recipient=email,
            template_name="organization_register/reset_password.html",
            context=context,
        )
        return Response(
            {"detail": "Password reset email sent."}, status=status.HTTP_200_OK
        )
