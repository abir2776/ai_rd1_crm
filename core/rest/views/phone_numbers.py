import json
import os

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from core.models import TwilioPhoneNumber

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_phone_number(request):
    """
    Buy a phone number from Twilio

    Expected JSON payload:
    {
        "area_code": "415",  # Optional
        "country": "US",     # Default: US
        "phone_number": "+14155551234"  # Optional: specific number to buy
    }

    Requires authentication.
    """
    try:
        data = request.data

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            return JsonResponse(
                {"error": "Twilio credentials not configured"}, status=500
            )

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        phone_number = data.get("phone_number")
        area_code = data.get("area_code")
        country = data.get("country", "US")

        if phone_number:
            purchased_number = client.incoming_phone_numbers.create(
                phone_number=phone_number
            )
            available_number = None
        else:
            search_params = {"country": country}
            if area_code:
                search_params["area_code"] = area_code

            available_numbers = client.available_phone_numbers(country).local.list(
                **search_params, limit=1
            )

            if not available_numbers:
                return JsonResponse(
                    {"error": "No available phone numbers found"}, status=404
                )

            available_number = available_numbers[0]
            purchased_number = client.incoming_phone_numbers.create(
                phone_number=available_number.phone_number
            )

        TwilioPhoneNumber.objects.create(
            organization=request.user.get_organization(),
            twilio_sid=purchased_number.sid,
            phone_number=purchased_number.phone_number,
            friendly_name=purchased_number.friendly_name or "",
            country_code=country,
            area_code=available_number.area_code if available_number else "",
            locality=available_number.locality if available_number else "",
            region=available_number.region if available_number else "",
            voice_capable=purchased_number.capabilities.get("voice", False),
            sms_capable=purchased_number.capabilities.get("SMS", False),
            mms_capable=purchased_number.capabilities.get("MMS", False),
            fax_capable=purchased_number.capabilities.get("fax", False),
        )

        return JsonResponse(
            {
                "success": True,
                "phone_number": purchased_number.phone_number,
                "sid": purchased_number.sid,
                "friendly_name": purchased_number.friendly_name,
                "capabilities": {
                    "voice": purchased_number.capabilities.get("voice", False),
                    "sms": purchased_number.capabilities.get("SMS", False),
                    "mms": purchased_number.capabilities.get("MMS", False),
                },
            },
            status=201,
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_phone_numbers(request):
    """
    Search for available phone numbers

    Query parameters:
    - area_code: Area code to search (e.g., 415)
    - country: Country code (default: US)
    - contains: Pattern the number should contain
    - limit: Number of results (default: 10, max: 30)

    Requires authentication.
    """
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            return JsonResponse(
                {"error": "Twilio credentials not configured"}, status=500
            )

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        area_code = request.GET.get("area_code")
        country = request.GET.get("country", "US")
        contains = request.GET.get("contains")
        limit = int(request.GET.get("limit", 10))

        search_params = {}
        if area_code:
            search_params["area_code"] = area_code
        if contains:
            search_params["contains"] = contains

        available_numbers = client.available_phone_numbers(country).local.list(
            **search_params, limit=min(limit, 30)
        )

        numbers = [
            {
                "phone_number": num.phone_number,
                "friendly_name": num.friendly_name,
                "locality": num.locality,
                "region": num.region,
                "capabilities": {
                    "voice": num.capabilities.get("voice", False),
                    "sms": num.capabilities.get("SMS", False),
                    "mms": num.capabilities.get("MMS", False),
                },
            }
            for num in available_numbers
        ]

        return JsonResponse(
            {"success": True, "count": len(numbers), "numbers": numbers}
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
