from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.choices import Status
from organizations.choices import OrganizationUserRole
from organizations.models import OrganizationUser
from organizations.rest.serializers.organizations import (
    MyOrganizationsSerializer,
    OrganizationSerializer,
)


class OrganizationProfileView(RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer

    def get_object(self):
        organization = (
            OrganizationUser.objects.filter(
                user=self.request.user, role=OrganizationUserRole.OWNER
            )
            .first()
            .organization
        )
        return organization


class MyOrganizationListView(ListAPIView):
    serializer_class = MyOrganizationsSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = OrganizationUser.objects.filter(user=user, status=Status.ACTIVE)
        return queryset


class OrganizationSwitchAPIView(APIView):
    def put(self, request, uid):
        organization_user = OrganizationUser.objects.filter(uid=uid).first()
        if organization_user == None:
            return Response(
                {"detail": "No account found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OrganizationUser.objects.filter(user=request.user, is_active=True).update(
            is_active=False
        )
        organization_user.is_active = True
        organization_user.save()
        return Response(
            {"detail": f"Account Switched To {organization_user.organization.name}"},
            status=status.HTTP_200_OK,
        )
