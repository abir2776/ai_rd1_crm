# urls.py
from django.urls import path

from ..views import phone_numbers

urlpatterns = [
    # List Views
    path("", phone_numbers.PhoneNumberListView.as_view(), name="phone_number_list"),
    path("countries", phone_numbers.countries, name="countries"),
    path(
        "available_phone_numbers",
        phone_numbers.available_phone_numbers,
        name="available-phone-numbers",
    ),
    path(
        "documents",
        phone_numbers.SupportingDocumentListView.as_view(),
        name="supporting_document_list",
    ),
    path(
        "addresses",
        phone_numbers.RegulatoryAddressListView.as_view(),
        name="address_list",
    ),
    path(
        "bundles", phone_numbers.RegulatoryBundleListView.as_view(), name="bundle_list"
    ),
    # Step 1: Subaccount Management
    path(
        "subaccounts/create", phone_numbers.create_subaccount, name="create_subaccount"
    ),
    # Step 2: End User Management (NEW - REQUIRED)
    path(
        "end-users/create",
        phone_numbers.create_end_user,
        name="create_end_user",
    ),
    # Step 3: Address Management
    path("addresses/create", phone_numbers.create_address, name="create_address"),
    # Step 4: Bundle Management
    path("bundles/create", phone_numbers.create_bundle, name="create_bundle"),
    path(
        "bundles/assign-end-user",
        phone_numbers.assign_end_user_to_bundle,
        name="assign_end_user_to_bundle",
    ),
    path(
        "bundles/assign-address",
        phone_numbers.assign_address_to_bundle,
        name="assign_address_to_bundle",
    ),
    path(
        "bundles/<str:bundle_id>/evaluate",
        phone_numbers.evaluate_bundle,
        name="evaluate_bundle",
    ),
    path(
        "bundles/<str:bundle_id>/status",
        phone_numbers.check_bundle_status,
        name="check_bundle_status",
    ),
    path("bundles/submit", phone_numbers.submit_bundle, name="submit_bundle"),
    # Step 5: Document Management
    path("documents/upload", phone_numbers.upload_document, name="upload_document"),
    # Step 6: Phone Number Management
    path(
        "search",
        phone_numbers.search_phone_numbers,
        name="search_phone_numbers",
    ),
    path("buy", phone_numbers.buy_phone_number, name="buy_phone_number"),
    path(
        "<str:phone_number_id>/release",
        phone_numbers.release_phone_number,
        name="release_phone_number",
    ),
    # Webhooks
    path(
        "webhooks/bundle-status",
        phone_numbers.bundle_status_webhook,
        name="bundle_status_webhook",
    ),
    # Workflow Status
    path("workflow-status", phone_numbers.get_workflow_status, name="workflow_status"),
]
