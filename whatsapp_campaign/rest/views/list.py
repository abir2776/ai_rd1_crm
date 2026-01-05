import requests
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.choices import Status
from organizations.models import OrganizationPlatform


def get_jobadder_contacts(access_token, base_url, name=None):
    url = f"{base_url}contacts"
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {}
    if name:
        params["name"] = name

    return requests.get(url, headers=headers, params=params)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jobadder_contacts_list(request):
    user = request.user
    organization = user.get_organization()

    platform = OrganizationPlatform.objects.filter(
        organization=organization,
        status=Status.ACTIVE,
    ).first()

    if not platform:
        return Response(
            {"error": "No connected platform found"},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    name = request.query_params.get("name")

    response = get_jobadder_contacts(
        platform.access_token,
        platform.base_url,
        name=name,
    )

    if response.status_code == 401:
        try:
            new_token = platform.refresh_access_token()
            response = get_jobadder_contacts(
                new_token,
                platform.base_url,
                name=name,
            )
        except Exception as e:
            return Response(
                {
                    "error": "Failed to refresh JobAdder token",
                    "details": str(e),
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    if response.status_code == 200:
        data = response.json()

        contacts = [
            {
                "id": item.get("contactId"),
                "first_name": item.get("firstName"),
                "last_name": item.get("lastName"),
                "email": item.get("email"),
                "phone": item.get("phone"),
            }
            for item in data.get("items", [])
        ]

        return Response(contacts, status=http_status.HTTP_200_OK)

    return Response(
        {
            "error": "Failed to fetch contacts",
            "details": response.text,
        },
        status=response.status_code,
    )
