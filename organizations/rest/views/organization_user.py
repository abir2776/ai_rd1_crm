from rest_framework.generics import ListAPIView
from organizations.rest.serializers.organization_user import (
    OrganizationUserSerializer,
)
from organizations.models import OrganizationUser
from organizations.choices import OrganizationUserRole


class OrganizationUserListView(ListAPIView):
    serializer_class = OrganizationUserSerializer

    def get_queryset(self):
        user = self.request.user
        user_role = user.get_role()
        organization = user.get_organization()
        queryset = OrganizationUser.objects.none()
        if user_role == OrganizationUserRole.OWNER:
            queryset = OrganizationUser.objects.filter(organization=organization)
        return queryset
