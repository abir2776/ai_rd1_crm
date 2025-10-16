from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
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
    def put(self, request, token):
        user = User.objects.get(token=token)
        user.is_verified = True
        return Response({"details": "User Verified"}, status=status.HTTP_200_OK)
