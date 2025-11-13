import requests
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.choices import Status
from organizations.models import OrganizationPlatform


def get_jobadder_status_list(access_token, base_url):
    url = f"{base_url}/applications/lists/status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    return requests.get(url, headers=headers)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jobadder_status_list(request):
    user = request.user
    organization = user.get_organization()
    platform = OrganizationPlatform.objects.filter(
        organization=organization, status=Status.ACTIVE
    ).first()
    if platform == None:
        return Response(
            {"error": "No connected platform found"},
            status=400,
        )
    response = get_jobadder_status_list(platform.access_token, platform.base_url)
    if response.status_code == 401:
        try:
            new_token = platform.refresh_access_token()
            response = get_jobadder_status_list(new_token, platform.base_url)
        except Exception as e:
            return Response(
                {"error": "Failed to refresh JobAdder token", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    if response.status_code == 200:
        data = response.json()
        statuses = [
            {"id": item.get("statusId"), "name": item.get("name")}
            for item in data.get("items", [])
        ]
        return Response(statuses, status=http_status.HTTP_200_OK)
    else:
        return Response(
            {"error": "Failed to fetch statuses", "details": response.text},
            status=response.status_code,
        )
