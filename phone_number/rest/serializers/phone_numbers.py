from rest_framework import serializers
from phone_number.models import (
    RegulatoryBundle,
    RegulatoryAddress,
    TwilioPhoneNumber,
    SupportingDocument,
)


class RegulatoryBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryBundle
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class RegulatoryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryAddress
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwilioPhoneNumber
        fields = ("__all__",)
        read_only_fields = ("__all__",)


class SupportingDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportingDocument
        fields = ("__all__",)
        read_only_fields = ("__all__",)
