from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationPlatform, Platform
from organizations.permissions import IsAdminOrOwner
from organizations.rest.serializers.organization_platform import (
    MyPlatformSerializer,
    OrganizationPlatformTokenSerializer,
    PlatformSerializer,
)


class ConnectPlatformView(APIView):
    permission_classes = [IsAdminOrOwner]

    def post(self, request):
        serializer = OrganizationPlatformTokenSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            org_platform = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Platform connected successfully",
                    "data": {
                        "platform": org_platform.platform.slug,
                        "platform_name": org_platform.platform.name,
                        "connected_at": org_platform.connected_at,
                        "is_connected": org_platform.is_connected,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PlatformListView(ListAPIView):
    permission_classes = [IsAdminOrOwner]
    serializer_class = PlatformSerializer
    queryset = Platform.objects.all()


class MyPlatformListView(ListAPIView):
    permission_classes = [IsAdminOrOwner]
    serializer_class = MyPlatformSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        queryset = OrganizationPlatform.objects.filter(organization=organization)
        return queryset
