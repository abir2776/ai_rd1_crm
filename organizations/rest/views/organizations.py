from rest_framework.generics import RetrieveUpdateAPIView
from organizations.rest.serializers.organizations import (
    OrganizationSerializer,
)
from organizations.models import Organization


class OrganizationProfileView(RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer

    def get_object(self):
        return self.request.user.get_organization()
