from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User
from organizations.choices import OrganizationUserRole
from organizations.models import OrganizationUser, OrganizationUserInvitation
from organizations.permissions import IsAdminOrOwner
from organizations.rest.serializers.organization_user_invite import (
    OrganizationUserInvitationSerializer,
)


class OrganizationUserInviteListCreateView(ListCreateAPIView):
    serializer_class = OrganizationUserInvitationSerializer
    permission_classes = [IsAdminOrOwner]

    def get_queryset(self):
        user = self.request.user
        user_role = user.get_role()
        organization = user.get_organization()
        queryset = OrganizationUserInvitation.objects.none()
        if user_role == OrganizationUserRole.OWNER:
            queryset = OrganizationUserInvitation.objects.filter(
                organization=organization
            )
        return queryset


class OrganizationUserInviteAcceptAPIView(APIView):
    permission_classes = [AllowAny]

    def put(self, request, token):
        invitation = OrganizationUserInvitation.objects.get(token=token)
        try:
            user = User.objects.get(email=invitation.email)
            OrganizationUser.objects.create(
                user=user, organization=invitation.organization, role=invitation.role
            )
            return Response(
                {"details": "Invitation Accepted"}, status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "User is not register yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
