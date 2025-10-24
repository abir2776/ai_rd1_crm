# views.py
import os

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from organizations.permissions import IsOwner
from phone_number.models import (
    RegulatoryAddress,
    RegulatoryBundle,
    SupportingDocument,
    TwilioPhoneNumber,
    TwilioSubAccount,
)

# Parent account credentials
TWILIO_PARENT_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_PARENT_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")


def get_twilio_client(account_sid=None, auth_token=None):
    """Get Twilio client with specified or parent credentials"""
    sid = account_sid or TWILIO_PARENT_ACCOUNT_SID
    token = auth_token or TWILIO_PARENT_AUTH_TOKEN
    return Client(sid, token)


# ============================================
# 1. CREATE SUBACCOUNT FOR CUSTOMER
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_phone_number(request):
    """
    Buy a phone number after bundle approval

    POST /api/twilio/phone-numbers/buy/
    {
        "phone_number": "+14155551234",  # Optional: specific number
        "area_code": "415",  # Optional: search by area code
        "country": "US",
        "bundle_id": "uuid",  # Required
        "address_id": "uuid"  # Required
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()

        # Get subaccount
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        # Get and validate bundle
        bundle_id = data.get("bundle_id")
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )

        if bundle.status != "TWILIO_APPROVED":
            return JsonResponse(
                {
                    "error": f"Bundle is not approved yet. Current status: {bundle.status}",
                    "message": "Please wait for bundle approval before purchasing phone numbers.",
                },
                status=400,
            )

        # Get and validate address
        address_id = data.get("address_id")
        address = get_object_or_404(
            RegulatoryAddress, uid=address_id, organization=organization
        )

        # Get Twilio client with subaccount credentials
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        phone_number = data.get("phone_number")
        area_code = data.get("area_code")
        country = data.get("country", "US")

        # Search for number if not provided
        if not phone_number:
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

            phone_number = available_numbers[0].phone_number

        # Purchase the phone number with bundle and address
        purchased_number = client.incoming_phone_numbers.create(
            phone_number=phone_number,
            bundle_sid=bundle.bundle_sid,
            address_sid=address.address_sid,
        )

        # Save to database
        db_phone_number = TwilioPhoneNumber.objects.create(
            organization=organization,
            subaccount=subaccount,
            bundle=bundle,
            address=address,
            twilio_sid=purchased_number.sid,
            phone_number=purchased_number.phone_number,
            friendly_name=purchased_number.friendly_name or "",
            country_code=country,
            number_type=bundle.number_type,
            voice_capable=purchased_number.capabilities.get("voice", False),
            sms_capable=purchased_number.capabilities.get("SMS", False),
            mms_capable=purchased_number.capabilities.get("MMS", False),
            fax_capable=purchased_number.capabilities.get("fax", False),
            status="ACTIVE",
            compliance_status="approved",
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Phone number purchased successfully!",
                "phone_number": {
                    "id": str(db_phone_number.uid),
                    "sid": purchased_number.sid,
                    "phone_number": purchased_number.phone_number,
                    "friendly_name": purchased_number.friendly_name,
                    "country_code": country,
                    "status": db_phone_number.status,
                    "capabilities": {
                        "voice": db_phone_number.voice_capable,
                        "sms": db_phone_number.sms_capable,
                        "mms": db_phone_number.mms_capable,
                    },
                    "bundle_sid": bundle.bundle_sid,
                    "address_sid": address.address_sid,
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 8. CHECK BUNDLE STATUS
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_bundle_status(request, bundle_id):
    """
    Check the status of a regulatory bundle

    GET /api/twilio/bundles/<bundle_id>/status/
    """
    try:
        user = request.user
        organization = user.get_organization()
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        subaccount = bundle.subaccount

        # Fetch current status from Twilio
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        twilio_bundle = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).fetch()

        # Map Twilio status to our status
        status_mapping = {
            "draft": "DRAFT",
            "pending-review": "PENDING_REVIEW",
            "in-review": "IN_REVIEW",
            "twilio-approved": "TWILIO_APPROVED",
            "twilio-rejected": "TWILIO_REJECTED",
        }

        new_status = status_mapping.get(twilio_bundle.status, bundle.status)

        # Update database if status changed
        if new_status != bundle.status:
            bundle.status = new_status
            if twilio_bundle.status == "twilio-rejected":
                bundle.rejection_reason = getattr(twilio_bundle, "failure_reason", "")
            bundle.save()

        return JsonResponse(
            {
                "success": True,
                "bundle": {
                    "id": str(bundle.uid),
                    "bundle_sid": bundle.bundle_sid,
                    "friendly_name": bundle.friendly_name,
                    "status": bundle.status,
                    "twilio_status": twilio_bundle.status,
                    "rejection_reason": bundle.rejection_reason
                    if bundle.status == "TWILIO_REJECTED"
                    else None,
                    "can_purchase_numbers": bundle.status == "TWILIO_APPROVED",
                },
            }
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 9. LIST USER'S PHONE NUMBERS
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_phone_numbers(request):
    """
    List all phone numbers for the authenticated user

    GET /api/twilio/phone-numbers/
    """
    try:
        user = request.user
        organization = user.get_organization()
        phone_numbers = TwilioPhoneNumber.objects.filter(organization=organization)

        numbers_data = [
            {
                "id": str(pn.uid),
                "sid": pn.twilio_sid,
                "phone_number": str(pn.phone_number),
                "friendly_name": pn.friendly_name,
                "country_code": pn.country_code,
                "status": pn.status,
                "compliance_status": pn.compliance_status,
                "capabilities": {
                    "voice": pn.voice_capable,
                    "sms": pn.sms_capable,
                    "mms": pn.mms_capable,
                },
                "is_primary": pn.is_primary,
                "purchase_date": pn.purchase_date.isoformat(),
            }
            for pn in phone_numbers
        ]

        return JsonResponse(
            {"success": True, "count": len(numbers_data), "phone_numbers": numbers_data}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 10. RELEASE PHONE NUMBER
# ============================================


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def release_phone_number(request, phone_number_id):
    """
    Release (delete) a phone number

    DELETE /api/twilio/phone-numbers/<phone_number_id>/release/
    """
    try:
        user = request.user
        organization = user.get_organization()
        phone_number = get_object_or_404(
            TwilioPhoneNumber, uid=phone_number_id, organization=organization
        )
        subaccount = phone_number.subaccount

        # Release number via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        client.incoming_phone_numbers(phone_number.twilio_sid).delete()

        # Update database
        from django.utils import timezone

        phone_number.status = "RELEASED"
        phone_number.release_date = timezone.now()
        phone_number.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Phone number released successfully",
                "phone_number": str(phone_number.phone_number),
            }
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 11. WEBHOOK: BUNDLE STATUS CALLBACK
# ============================================


@csrf_exempt
@api_view(["POST"])
def bundle_status_webhook(request):
    """
    Webhook endpoint for Twilio bundle status updates

    POST /api/twilio/webhooks/bundle-status/

    Configure this URL in your bundle creation:
    status_callback = "https://yourdomain.com/api/twilio/webhooks/bundle-status/"
    """
    try:
        data = request.data

        bundle_sid = data.get("BundleSid")
        status = data.get("Status")

        # Find bundle in database
        bundle = RegulatoryBundle.objects.filter(bundle_sid=bundle_sid).first()

        if not bundle:
            return JsonResponse({"error": "Bundle not found"}, status=404)

        # Map Twilio status
        status_mapping = {
            "draft": "DRAFT",
            "pending-review": "PENDING_REVIEW",
            "in-review": "IN_REVIEW",
            "twilio-approved": "TWILIO_APPROVED",
            "twilio-rejected": "TWILIO_REJECTED",
        }

        new_status = status_mapping.get(status, bundle.status)
        bundle.status = new_status

        if status == "twilio-rejected":
            bundle.rejection_reason = data.get("FailureReason", "")

        bundle.save()

        # TODO: Send notification to user (email, push notification, etc.)

        return JsonResponse(
            {
                "success": True,
                "message": "Bundle status updated",
                "bundle_sid": bundle_sid,
                "new_status": new_status,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 12. GET COMPLETE WORKFLOW STATUS
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_workflow_status(request):
    """
    Get complete workflow status for user

    GET /api/twilio/workflow-status/
    """
    try:
        user = request.user
        organization = user.get_organization()

        # Check subaccount
        subaccount = TwilioSubAccount.objects.filter(organization=organization).first()

        # Check address
        address = RegulatoryAddress.objects.filter(organization=organization).first()

        # Check bundles
        bundles = RegulatoryBundle.objects.filter(organization=organization)
        approved_bundle = bundles.filter(status="TWILIO_APPROVED").first()

        # Check phone numbers
        phone_numbers = TwilioPhoneNumber.objects.filter(
            organization=organization, status="ACTIVE"
        )

        workflow_status = {
            "step_1_subaccount": {
                "completed": bool(subaccount),
                "data": {
                    "account_sid": subaccount.twilio_account_sid
                    if subaccount
                    else None,
                    "status": subaccount.status if subaccount else None,
                }
                if subaccount
                else None,
            },
            "step_2_address": {
                "completed": bool(address),
                "data": {
                    "address_sid": address.address_sid if address else None,
                    "status": address.status if address else None,
                }
                if address
                else None,
            },
            "step_3_bundle": {
                "completed": bool(approved_bundle),
                "pending": bundles.filter(
                    status__in=["PENDING_REVIEW", "IN_REVIEW"]
                ).exists(),
                "data": [
                    {
                        "bundle_sid": b.bundle_sid,
                        "status": b.status,
                        "can_purchase": b.status == "TWILIO_APPROVED",
                    }
                    for b in bundles
                ],
            },
            "step_4_phone_numbers": {
                "completed": phone_numbers.exists(),
                "count": phone_numbers.count(),
                "data": [
                    {"phone_number": str(pn.phone_number), "status": pn.status}
                    for pn in phone_numbers
                ],
            },
            "can_purchase_numbers": bool(approved_bundle),
            "next_step": _get_next_step(
                subaccount, address, approved_bundle, phone_numbers
            ),
        }

        return JsonResponse({"success": True, "workflow": workflow_status})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def _get_next_step(subaccount, address, approved_bundle, phone_numbers):
    """Helper to determine next step in workflow"""
    if not subaccount:
        return "Create subaccount"
    if not address:
        return "Create address"
    if not approved_bundle:
        return "Create and submit bundle for approval"
    if not phone_numbers.exists():
        return "Purchase phone number"
    return "All steps completed"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_subaccount(request):
    """
    Create a Twilio subaccount for a customer

    POST /api/twilio/subaccounts/create/
    {
        "user_id": 123,
        "friendly_name": "Customer Name"
    }
    """
    try:
        data = request.data
        user = request.user
        organization_id = user.get_organization().id
        friendly_name = data.get("friendly_name", f"Customer {organization_id}")

        # Check if subaccount already exists
        if TwilioSubAccount.objects.filter(organization_id=organization_id).exists():
            return JsonResponse(
                {"error": "Subaccount already exists for this user"}, status=400
            )

        # Create subaccount via Twilio API
        client = get_twilio_client()
        subaccount = client.api.accounts.create(friendly_name=friendly_name)

        # Save to database
        db_subaccount = TwilioSubAccount.objects.create(
            organization_id=organization_id,
            twilio_account_sid=subaccount.sid,
            twilio_auth_token=subaccount.auth_token,
            friendly_name=friendly_name,
        )

        return JsonResponse(
            {
                "success": True,
                "subaccount": {
                    "id": str(db_subaccount.uid),
                    "account_sid": subaccount.sid,
                    "auth_token": subaccount.auth_token,
                    "friendly_name": friendly_name,
                    "status": db_subaccount.status,
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 2. CREATE ADDRESS (Required for compliance)
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_address(request):
    """
    Create a regulatory address for phone number compliance

    POST /api/twilio/addresses/create/
    {
        "customer_name": "John Doe",
        "street": "123 Main St",
        "city": "San Francisco",
        "region": "CA",
        "postal_code": "94102",
        "iso_country": "US"
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()

        # Get user's subaccount
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        # Create address via Twilio API using subaccount credentials
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        address = client.addresses.create(
            customer_name=data.get("customer_name"),
            street=data.get("street"),
            city=data.get("city"),
            region=data.get("region"),
            postal_code=data.get("postal_code"),
            iso_country=data.get("iso_country"),
            street_secondary=data.get("street_secondary", ""),
            friendly_name=data.get("friendly_name", "Primary Address"),
        )

        # Save to database
        db_address = RegulatoryAddress.objects.create(
            organization=organization,
            subaccount=subaccount,
            address_sid=address.sid,
            friendly_name=address.friendly_name,
            customer_name=data.get("customer_name"),
            street=data.get("street"),
            street_secondary=data.get("street_secondary", ""),
            city=data.get("city"),
            region=data.get("region"),
            postal_code=data.get("postal_code"),
            iso_country=data.get("iso_country"),
            status="VERIFIED",
        )

        return JsonResponse(
            {
                "success": True,
                "address": {
                    "id": str(db_address.uid),
                    "address_sid": address.sid,
                    "customer_name": db_address.customer_name,
                    "street": db_address.street,
                    "city": db_address.city,
                    "region": db_address.region,
                    "postal_code": db_address.postal_code,
                    "iso_country": db_address.iso_country,
                    "status": db_address.status,
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 3. CREATE REGULATORY BUNDLE
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_bundle(request):
    """
    Create a regulatory bundle for phone number compliance

    POST /api/twilio/bundles/create/
    {
        "friendly_name": "US Local Business Bundle",
        "iso_country": "US",
        "number_type": "local",
        "end_user_type": "business",
        "email": "customer@example.com"
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()

        # Get user's subaccount
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        # Create bundle via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        bundle = client.numbers.v2.regulatory_compliance.bundles.create(
            friendly_name=data.get("friendly_name"),
            email=data.get("email"),
            status_callback=data.get("status_callback_url", ""),
            regulation_sid=data.get("regulation_sid", ""),
            iso_country=data.get("iso_country"),
            number_type=data.get("number_type"),
            end_user_type=data.get("end_user_type", "business"),
        )

        # Save to database
        db_bundle = RegulatoryBundle.objects.create(
            organization=organization,
            subaccount=subaccount,
            bundle_sid=bundle.sid,
            friendly_name=data.get("friendly_name"),
            iso_country=data.get("iso_country"),
            number_type=data.get("number_type"),
            end_user_type=data.get("end_user_type", "business"),
            email=data.get("email"),
            status="DRAFT",
        )

        return JsonResponse(
            {
                "success": True,
                "bundle": {
                    "id": str(db_bundle.uid),
                    "bundle_sid": bundle.sid,
                    "friendly_name": db_bundle.friendly_name,
                    "iso_country": db_bundle.iso_country,
                    "number_type": db_bundle.number_type,
                    "status": bundle.status,
                    "message": "Bundle created. Please upload required documents and submit for review.",
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 4. UPLOAD SUPPORTING DOCUMENTS
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_document(request):
    """
    Upload supporting document for regulatory bundle

    POST /api/twilio/documents/upload/
    Form Data:
    - bundle_id: UUID of the bundle
    - document_type: Type of document (e.g., "passport", "business_license")
    - file: Document file
    """
    try:
        user = request.user
        organization = user.get_organization()
        bundle_id = request.data.get("bundle_id")
        document_type = request.data.get("document_type")
        file = request.FILES.get("file")

        if not file:
            return JsonResponse({"error": "No file provided"}, status=400)

        # Get bundle
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )

        # Get subaccount
        subaccount = bundle.subaccount

        # Upload document to Twilio
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        # Create supporting document
        document = client.numbers.v2.regulatory_compliance.supporting_documents.create(
            friendly_name=file.name,
            type=document_type,
            attributes={"file": file.read()},
        )

        # Assign document to bundle
        client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=document.sid)

        # Save to database
        db_document = SupportingDocument.objects.create(
            organization=organization,
            bundle=bundle,
            document_sid=document.sid,
            document_type=document_type,
            friendly_name=file.name,
            file=file,
            mime_type=file.content_type,
        )

        return JsonResponse(
            {
                "success": True,
                "document": {
                    "id": str(db_document.uid),
                    "document_sid": document.sid,
                    "document_type": document_type,
                    "filename": file.name,
                    "status": "uploaded",
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 5. SUBMIT BUNDLE FOR REVIEW
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_bundle(request):
    """
    Submit bundle for Twilio review

    POST /api/twilio/bundles/submit/
    {
        "bundle_id": "uuid"
    }
    """
    try:
        user = request.user
        organization = user.get_organization()
        bundle_id = request.data.get("bundle_id")

        # Get bundle
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        subaccount = bundle.subaccount

        # Submit bundle via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        updated_bundle = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).update(status="pending-review")

        # Update database
        bundle.status = "PENDING_REVIEW"
        bundle.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Bundle submitted for review. This may take up to 3 business days.",
                "bundle_sid": bundle.bundle_sid,
                "status": updated_bundle.status,
            }
        )

    except TwilioRestException as e:
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 6. SEARCH AVAILABLE PHONE NUMBERS
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_phone_numbers(request):
    """
    Search for available phone numbers

    GET /api/twilio/phone-numbers/search/?area_code=415&country=US
    """
    try:
        user = request.user
        organization = user.get_organization()
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        area_code = request.GET.get("area_code")
        country = request.GET.get("country", "US")
        contains = request.GET.get("contains")
        limit = int(request.GET.get("limit", 10))

        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

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
