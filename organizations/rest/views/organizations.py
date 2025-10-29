from rest_framework.generics import RetrieveUpdateAPIView

from organizations.rest.serializers.organizations import (
    OrganizationSerializer,
)
from organizations.models import OrganizationUser
from organizations.choices import OrganizationUserRole


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
