from rest_framework.generics import RetrieveUpdateAPIView

from organizations.permissions import IsAdminOrOwner
from organizations.rest.serializers.organizations import (
    OrganizationSerializer,
)


class OrganizationProfileView(RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAdminOrOwner]

    def get_object(self):
        return self.request.user.get_organization()
