# views.py
import json
import logging
import os

import requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from requests.auth import HTTPBasicAuth
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from phone_number.models import (
    EndUser,
    RegulatoryAddress,
    RegulatoryBundle,
    SupportingDocument,
    TwilioPhoneNumber,
    TwilioSubAccount,
)
from phone_number.rest.serializers.phone_numbers import (
    PhoneNumberSerializer,
    RegulatoryAddressSerializer,
    RegulatoryBundleSerializer,
    SupportingDocumentSerializer,
)

logger = logging.getLogger(__name__)

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
def create_subaccount(request):
    """
    Create a Twilio subaccount for a customer

    POST /api/twilio/subaccounts/create/
    {
        "friendly_name": "Customer Name"
    }
    """
    try:
        data = request.data
        user = request.user
        organization = user.get_organization()
        friendly_name = data.get("friendly_name", f"Customer {organization.id}")

        # Check if subaccount already exists
        if TwilioSubAccount.objects.filter(organization=organization).exists():
            return JsonResponse(
                {"details": "Subaccount already exists for this organization"},
                status=200,
            )

        # Create subaccount via Twilio API
        client = get_twilio_client()
        subaccount = client.api.accounts.create(friendly_name=friendly_name)

        # Save to database
        db_subaccount = TwilioSubAccount.objects.create(
            organization=organization,
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
                    "friendly_name": friendly_name,
                    "status": db_subaccount.status,
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error creating subaccount: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error creating subaccount: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 2. CREATE END USER (NEW - Required for Bundle)
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_end_user(request):
    """
    Create an End User for regulatory compliance

    POST /api/twilio/end-users/create/
    {
        "friendly_name": "My Company LLC",

        # For business type:
        "business_name": "My Company LLC",
        "business_registration_number": "123456789",
        "business_registration_identifier": "EIN",  # EIN, VAT, ABN, etc.
        "business_website": "https://mycompany.com",

        # Authorized representative:
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@mycompany.com",
        "phone_number": "+14155551234",

        "bundle_id": UUID of bundle
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()
        bundle_id = data.get("bundle_id")

        # Get user's subaccount
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        # Create end user via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        end_user_type = "business"

        # Prepare attributes based on end user type
        attributes = {
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone_number": data.get("phone_number"),
        }

        # Add business-specific attributes
        if end_user_type == "business":
            attributes.update(
                {
                    "business_name": data.get("business_name"),
                    "business_registration_number": data.get(
                        "business_registration_number"
                    ),
                    "business_registration_identifier": data.get(
                        "business_registration_identifier", "EIN"
                    ),
                    "business_website": data.get("business_website"),
                    "business_identity": "DIRECT_CUSTOMER",
                    "is_subassigned": "YES",
                }
            )

        # Create end user in Twilio
        end_user = client.numbers.v2.regulatory_compliance.end_users.create(
            friendly_name=data.get(
                "friendly_name", f"{data.get('first_name')} {data.get('last_name')}"
            ),
            type=end_user_type,
            attributes=attributes,
        )
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=end_user.sid)

        # Save to database
        db_end_user = EndUser.objects.create(
            organization=organization,
            subaccount=subaccount,
            end_user_sid=end_user.sid,
            friendly_name=data.get(
                "friendly_name", f"{data.get('first_name')} {data.get('last_name')}"
            ),
            end_user_type=end_user_type,
            business_name=data.get("business_name", ""),
            business_registration_number=data.get("business_registration_number", ""),
            business_registration_identifier=data.get(
                "business_registration_identifier", ""
            ),
            business_website=data.get("business_website", ""),
            business_identity=data.get("business_identity", ""),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            phone_number=data.get("phone_number"),
            is_subassigned=data.get("is_subassigned", False),
            comments=data.get("comments", ""),
        )

        return JsonResponse(
            {
                "success": True,
                "end_user": {
                    "id": str(db_end_user.uid),
                    "end_user_sid": end_user.sid,
                    "friendly_name": db_end_user.friendly_name,
                    "type": end_user_type,
                    "status": "created",
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error creating end user: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code},
            status=400,
        )
    except Exception as e:
        logger.error(f"Error creating end user: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 3. CREATE ADDRESS
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
        "iso_country": "US",

        "bundle_id": UUID of bundle
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()
        bundle_id = data.get("bundle_id")

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
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        supporting_doc = (
            client.numbers.v2.regulatory_compliance.supporting_documents.create(
                friendly_name=bundle.friendly_name,
                type="business_address",
                attributes={
                    "address_sids": [address.sid],
                },
            )
        )
        client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=supporting_doc.sid)
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
        logger.error(f"Twilio error creating address: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error creating address: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 4. CREATE REGULATORY BUNDLE (UPDATED)
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

        # Get or validate end user
        end_user_id = data.get("end_user_id")
        end_user = None
        if end_user_id:
            end_user = get_object_or_404(
                EndUser, uid=end_user_id, organization=organization
            )

        # Create bundle via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        callback_url = request.build_absolute_uri(
            "/api/v1/phone_number/webhooks/bundle-status"
        )

        bundle = client.numbers.v2.regulatory_compliance.bundles.create(
            friendly_name=data.get("friendly_name"),
            email=data.get("email"),
            status_callback=callback_url,
            iso_country=data.get("iso_country"),
            number_type=data.get("number_type"),
            end_user_type="business",
        )

        # Save to database
        db_bundle = RegulatoryBundle.objects.create(
            organization=organization,
            subaccount=subaccount,
            end_user=end_user,
            bundle_sid=bundle.sid,
            friendly_name=data.get("friendly_name"),
            iso_country=data.get("iso_country"),
            number_type=data.get("number_type"),
            end_user_type="business",
            email=data.get("email"),
            status="DRAFT",
            status_callback_url=callback_url,
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
                    "message": "Bundle created. Next steps: 1) Assign End User, 2) Assign Address, 3) Upload documents, 4) Submit for review.",
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error creating bundle: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error creating bundle: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 5. ASSIGN END USER TO BUNDLE (NEW)
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_end_user_to_bundle(request):
    """
    Assign an End User to a Bundle

    POST /api/twilio/bundles/assign-end-user/
    {
        "bundle_id": "uuid",
        "end_user_id": "uuid"
    }
    """
    try:
        user = request.user
        organization = user.get_organization()

        bundle_id = request.data.get("bundle_id")
        end_user_id = request.data.get("end_user_id")

        # Get bundle and end user
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        end_user = get_object_or_404(
            EndUser, uid=end_user_id, organization=organization
        )

        subaccount = bundle.subaccount

        # Assign end user to bundle via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        assignment = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=end_user.end_user_sid)

        # Update database
        bundle.end_user = end_user
        bundle.save()

        return JsonResponse(
            {
                "success": True,
                "message": "End User assigned to bundle successfully",
                "assignment_sid": assignment.sid,
            }
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error assigning end user: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error assigning end user: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 6. ASSIGN ADDRESS TO BUNDLE (NEW)
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_address_to_bundle(request):
    """
    Assign a verified Address to a Regulatory Bundle in Twilio.
    """
    try:
        user = request.user
        organization = user.get_organization()

        bundle_id = request.data.get("bundle_id")
        address_id = request.data.get("address_id")

        # Get bundle and address
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        address = get_object_or_404(
            RegulatoryAddress, uid=address_id, organization=organization
        )

        subaccount = bundle.subaccount
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        # ✅ Assign the address to the bundle
        assignment = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=address.address_sid)

        return JsonResponse(
            {
                "success": True,
                "message": "Address assigned to bundle successfully",
                "assignment_sid": assignment.sid,
            }
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error assigning address: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code},
            status=400,
        )
    except Exception as e:
        logger.error(f"Error assigning address: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 7. UPLOAD SUPPORTING DOCUMENTS
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_document(request):
    """
    Upload supporting document for regulatory bundle

    POST /api/twilio/documents/upload/
    Form Data:
    - bundle_id: UUID of the bundle
    - address_id: UUID of address
    - document_type: Type of document (e.g., "passport", "business_license")
    - file: Document file
    """
    try:
        user = request.user
        organization = user.get_organization()
        bundle_id = request.data.get("bundle_id")
        address_id = request.data.get("address_id")
        document_type = request.data.get("document_type")
        file = request.FILES.get("file")

        if not file:
            return JsonResponse({"error": "No file provided"}, status=400)

        # Get bundle
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        address = get_object_or_404(
            RegulatoryAddress, uid=address_id, organization=organization
        )

        # Get subaccount
        subaccount = bundle.subaccount

        # Read file content once
        file_content = file.read()

        # Upload document to Twilio using direct HTTP API
        url = "https://numbers.twilio.com/v2/RegulatoryCompliance/SupportingDocuments"

        # Prepare the multipart form data
        files = {"File": (file.name, file_content, file.content_type)}

        data = {
            "FriendlyName": file.name,
            "Type": document_type,
            "Attributes": json.dumps({"address_sids": [address.address_sid]}),
        }

        # Make the request with basic auth
        response = requests.post(
            url,
            auth=HTTPBasicAuth(
                subaccount.twilio_account_sid, subaccount.twilio_auth_token
            ),
            data=data,
            files=files,
        )

        if response.status_code not in [200, 201]:
            error_message = (
                response.json().get("message", "Unknown error")
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else response.text
            )
            return JsonResponse({"error": f"Twilio error: {error_message}"}, status=400)

        document_data = response.json()
        document_sid = document_data.get("sid")

        # Assign document to bundle using the SDK
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).item_assignments.create(object_sid=document_sid)

        # Save to database WITHOUT the file (it's already on Twilio)
        db_document = SupportingDocument.objects.create(
            organization=organization,
            bundle=bundle,
            document_sid=document_sid,
            document_type=document_type,
            friendly_name=file.name,
            mime_type=file.content_type,
        )

        return JsonResponse(
            {
                "success": True,
                "document": {
                    "id": str(db_document.uid),
                    "document_sid": document_sid,
                    "document_type": document_type,
                    "filename": file.name,
                    "status": "uploaded",
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error uploading document: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 8. EVALUATE BUNDLE BEFORE SUBMISSION (NEW)
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evaluate_bundle(request, bundle_id):
    """
    Evaluate bundle to check if it's ready for submission

    GET /api/twilio/bundles/<bundle_id>/evaluate/
    """
    try:
        user = request.user
        organization = user.get_organization()

        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        subaccount = bundle.subaccount

        # Evaluate bundle via Twilio API
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        evaluation = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).evaluations.create()

        # Parse evaluation results
        results = evaluation.results
        is_compliant = evaluation.status == "compliant"

        issues = []
        if not is_compliant:
            for result in results:
                if not result.get("passed"):
                    requirement_name = result.get("requirement_friendly_name")
                    invalid_fields = result.get("invalid", [])

                    for field in invalid_fields:
                        issues.append(
                            {
                                "requirement": requirement_name,
                                "field": field.get("friendly_name"),
                                "error": field.get("failure_reason"),
                            }
                        )

        return JsonResponse(
            {
                "success": True,
                "bundle_sid": bundle.bundle_sid,
                "is_compliant": is_compliant,
                "status": evaluation.status,
                "can_submit": is_compliant,
                "issues": issues,
                "message": "Bundle is ready for submission!"
                if is_compliant
                else "Please fix the following issues before submitting:",
            }
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error evaluating bundle: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error evaluating bundle: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 9. SUBMIT BUNDLE FOR REVIEW
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_bundle(request):
    """
    Submit bundle for Twilio review (after evaluation passes)

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

        # First, evaluate the bundle
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        evaluation = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).evaluations.create()

        if evaluation.status != "compliant":
            # Parse errors
            issues = []
            for result in evaluation.results:
                if not result.get("passed"):
                    requirement_name = result.get("requirement_friendly_name")
                    invalid_fields = result.get("invalid", [])

                    for field in invalid_fields:
                        issues.append(
                            {
                                "requirement": requirement_name,
                                "field": field.get("friendly_name"),
                                "error": field.get("failure_reason"),
                            }
                        )

            return JsonResponse(
                {
                    "error": "Bundle is not compliant",
                    "message": "Please fix the following issues before submitting:",
                    "issues": issues,
                },
                status=400,
            )

        # Submit bundle via Twilio API
        updated_bundle = client.numbers.v2.regulatory_compliance.bundles(
            bundle.bundle_sid
        ).update(status="pending-review")

        # Update database
        bundle.status = "PENDING_REVIEW"
        bundle.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Bundle submitted for review successfully! This may take up to 3 business days.",
                "bundle_sid": bundle.bundle_sid,
                "status": updated_bundle.status,
            }
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error submitting bundle: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error submitting bundle: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 10. CHECK BUNDLE STATUS
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
        logger.error(f"Twilio error checking bundle status: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error checking bundle status: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 11. SEARCH AVAILABLE PHONE NUMBERS
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
        logger.error(f"Twilio error searching numbers: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error searching numbers: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 12. BUY PHONE NUMBER
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_phone_number(request):
    """
    Buy a Twilio phone number (requires approved bundle and address)

    POST /api/twilio/phone-numbers/buy/
    {
        "phone_number": "+14155551234",   # Required
        "bundle_id": "uuid",              # Required (RegulatoryBundle.uid)
    }
    """
    try:
        user = request.user
        data = request.data
        organization = user.get_organization()

        # --- Validate required fields ---
        phone_number = data.get("phone_number")
        bundle_id = data.get("bundle_id")

        if not phone_number or not bundle_id:
            return JsonResponse(
                {"error": "phone_number, bundle_id are required fields."},
                status=400,
            )

        # --- Get Subaccount ---
        subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

        # --- Get Bundle ---
        bundle = get_object_or_404(
            RegulatoryBundle, uid=bundle_id, organization=organization
        )
        if bundle.status != "TWILIO_APPROVED":
            return JsonResponse(
                {
                    "error": f"Bundle not approved yet. Current status: {bundle.status}",
                    "message": "Please wait for bundle approval before purchasing.",
                },
                status=400,
            )
        # --- Get Twilio client ---
        client = get_twilio_client(
            subaccount.twilio_account_sid, subaccount.twilio_auth_token
        )

        # --- Purchase phone number ---
        purchased_number = client.incoming_phone_numbers.create(
            phone_number=phone_number, bundle_sid=bundle.bundle_sid
        )

        # --- Save in DB ---
        db_phone_number = TwilioPhoneNumber.objects.create(
            organization=organization,
            subaccount=subaccount,
            bundle=bundle,
            twilio_sid=purchased_number.sid,
            phone_number=purchased_number.phone_number,
            friendly_name=purchased_number.friendly_name or "",
            country_code=purchased_number.iso_country,
            number_type=bundle.number_type,
            voice_capable=purchased_number.capabilities.get("voice", False),
            sms_capable=purchased_number.capabilities.get("SMS", False),
            mms_capable=purchased_number.capabilities.get("MMS", False),
            fax_capable=purchased_number.capabilities.get("fax", False),
            status="ACTIVE",
            compliance_status="approved",
        )

        # --- Response ---
        return JsonResponse(
            {
                "success": True,
                "message": "Phone number purchased successfully!",
                "phone_number": {
                    "id": str(db_phone_number.uid),
                    "sid": purchased_number.sid,
                    "phone_number": purchased_number.phone_number,
                    "friendly_name": purchased_number.friendly_name,
                    "country_code": purchased_number.iso_country,
                    "status": db_phone_number.status,
                    "capabilities": {
                        "voice": db_phone_number.voice_capable,
                        "sms": db_phone_number.sms_capable,
                        "mms": db_phone_number.mms_capable,
                        "fax": db_phone_number.fax_capable,
                    },
                    "bundle_sid": bundle.bundle_sid,
                },
            },
            status=201,
        )

    except TwilioRestException as e:
        logger.error(f"Twilio error buying phone number: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )

    except Exception as e:
        logger.error(f"Error buying phone number: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 13. LIST USER'S PHONE NUMBERS
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
        logger.error(f"Error listing phone numbers: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 14. RELEASE PHONE NUMBER
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
        logger.error(f"Twilio error releasing phone number: {e.msg}")
        return JsonResponse(
            {"error": f"Twilio error: {e.msg}", "code": e.code}, status=400
        )
    except Exception as e:
        logger.error(f"Error releasing phone number: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 15. WEBHOOK: BUNDLE STATUS CALLBACK
# ============================================


@csrf_exempt
@api_view(["POST"])
def bundle_status_webhook(request):
    """
    Webhook endpoint for Twilio bundle status updates

    POST /api/twilio/webhooks/bundle-status/
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

        logger.info(f"Bundle {bundle_sid} status updated to {new_status}")

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
        logger.error(f"Error in bundle status webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# 16. GET COMPLETE WORKFLOW STATUS
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

        # Check end users
        end_user = EndUser.objects.filter(organization=organization).first()

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
            "step_2_end_user": {
                "completed": bool(end_user),
                "data": {
                    "end_user_sid": end_user.end_user_sid if end_user else None,
                    "type": end_user.end_user_type if end_user else None,
                }
                if end_user
                else None,
            },
            "step_3_address": {
                "completed": bool(address),
                "data": {
                    "address_sid": address.address_sid if address else None,
                    "status": address.status if address else None,
                }
                if address
                else None,
            },
            "step_4_bundle": {
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
            "step_5_phone_numbers": {
                "completed": phone_numbers.exists(),
                "count": phone_numbers.count(),
                "data": [
                    {"phone_number": str(pn.phone_number), "status": pn.status}
                    for pn in phone_numbers
                ],
            },
            "can_purchase_numbers": bool(approved_bundle),
            "next_step": _get_next_step(
                subaccount, end_user, address, approved_bundle, phone_numbers
            ),
        }

        return JsonResponse({"success": True, "workflow": workflow_status})

    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def _get_next_step(subaccount, end_user, address, approved_bundle, phone_numbers):
    """Helper to determine next step in workflow"""
    if not subaccount:
        return "Create subaccount"
    if not end_user:
        return "Create end user (business information)"
    if not address:
        return "Create address"
    if not approved_bundle:
        return "Create bundle, assign end user & address, upload documents, and submit for approval"
    if not phone_numbers.exists():
        return "Purchase phone number"
    return "All steps completed"


# ============================================
# LIST VIEWS FOR API
# ============================================


class RegulatoryBundleListView(generics.ListAPIView):
    serializer_class = RegulatoryBundleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return RegulatoryBundle.objects.filter(organization=organization)


class RegulatoryAddressListView(generics.ListAPIView):
    serializer_class = RegulatoryAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return RegulatoryAddress.objects.filter(organization=organization)


class PhoneNumberListView(generics.ListAPIView):
    serializer_class = PhoneNumberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return TwilioPhoneNumber.objects.filter(organization=organization)


class SupportingDocumentListView(generics.ListAPIView):
    serializer_class = SupportingDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return SupportingDocument.objects.filter(organization=organization)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def countries(request):
    user = request.user
    organization = user.get_organization()
    subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

    url = (
        "https://api.twilio.com/2010-04-01/Accounts/"
        f"{subaccount.twilio_account_sid}/AvailablePhoneNumbers.json"
    )
    auth = (subaccount.twilio_account_sid, subaccount.twilio_auth_token)

    try:
        resp = requests.get(url, auth=auth, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return HttpResponse(f"Error fetching from Twilio: {e}", status=502)

    data = resp.json()
    countries = data.get("countries", [])

    # --- 🔍 Search Support ---
    search_query = request.GET.get("search", "").strip().lower()
    if search_query:
        countries = [
            c
            for c in countries
            if search_query in c.get("country", "").lower()
            or search_query in c.get("country_code", "").lower()
        ]

    return JsonResponse({"countries": countries}, safe=False)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def available_phone_numbers(request):
    country_code = request.GET.get("country", None)
    if country_code == None:
        return HttpResponse("Country code is required", status=400)
    user = request.user
    organization = user.get_organization()
    subaccount = get_object_or_404(TwilioSubAccount, organization=organization)

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{subaccount.twilio_account_sid}/AvailablePhoneNumbers/{country_code}/Local.json"
    )
    auth = (subaccount.twilio_account_sid, subaccount.twilio_auth_token)

    search_query = request.GET.get("search", "").strip()

    params = {}
    if search_query:
        params["Contains"] = search_query

    try:
        resp = requests.get(url, auth=auth, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return HttpResponse(
            f"Error fetching phone numbers from Twilio: {e}", status=502
        )

    data = resp.json()
    phone_numbers = data.get("available_phone_numbers", [])

    return JsonResponse({"phone_numbers": phone_numbers}, safe=False)
