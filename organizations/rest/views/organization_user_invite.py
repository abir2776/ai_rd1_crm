from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from organizations.rest.serializers.organization_user_invite import (
    OrganizationUserInvitationSerializer,
)
from organizations.models import OrganizationUserInvitation, OrganizationUser
from core.models import User
from organizations.choices import OrganizationUserRole


class OrganizationUserInviteListCreateView(ListCreateAPIView):
    serializer_class = OrganizationUserInvitationSerializer

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
    def put(self, request, token):
        invitation = OrganizationUserInvitation.objects.get(token=token)
        user = User.objects.get(email=invitation.email)
        OrganizationUser.objects.create(
            user=user, organization=invitation.organization, role=invitation.role
        )
        return Response({"details": "Invitation Accepted"}, status=status.HTTP_200_OK)
