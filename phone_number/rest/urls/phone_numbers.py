# urls.py
from django.urls import path

from ..views import phone_numbers

urlpatterns = [
    # Subaccount Management
    path(
        "subaccounts/create", phone_numbers.create_subaccount, name="create_subaccount"
    ),
    # Address Management
    path("addresses/create", phone_numbers.create_address, name="create_address"),
    # Bundle Management
    path("bundles/create", phone_numbers.create_bundle, name="create_bundle"),
    path(
        "bundles/<str:bundle_id>/status",
        phone_numbers.check_bundle_status,
        name="check_bundle_status",
    ),
    path("bundles/submit", phone_numbers.submit_bundle, name="submit_bundle"),
    # Document Management
    path("documents/upload", phone_numbers.upload_document, name="upload_document"),
    # Phone Number Management
    path(
        "search",
        phone_numbers.search_phone_numbers,
        name="search_phone_numbers",
    ),
    path("buy", phone_numbers.buy_phone_number, name="buy_phone_number"),
    path("", phone_numbers.list_phone_numbers, name="list_phone_numbers"),
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
