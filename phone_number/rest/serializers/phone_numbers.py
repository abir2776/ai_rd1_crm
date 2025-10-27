from rest_framework import serializers

from phone_number.models import (
    RegulatoryAddress,
    RegulatoryBundle,
    SupportingDocument,
    TwilioPhoneNumber,
)


class RegulatoryBundleSerializer(serializers.ModelSerializer):
    class meta:
        model = RegulatoryBundle
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class RegulatoryAddressSerializer(serializers.ModelSerializer):
    class meta:
        model = RegulatoryAddress
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class PhoneNumberSerializer(serializers.ModelSerializer):
    class meta:
        model = TwilioPhoneNumber
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class SupportingDocumentSerializer(serializers.ModelSerializer):
    class meta:
        model = SupportingDocument
        fields = ("__all__",)
        read_only_fields = ("__all__",)
