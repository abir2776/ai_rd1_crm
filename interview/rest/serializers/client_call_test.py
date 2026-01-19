# calls/serializers.py
from rest_framework import serializers

from interview.models import CallRequest, MeetingBooking


class CallRequestSerializer(serializers.ModelSerializer):
    scheduled_at = serializers.DateTimeField(required=False)
    company_name = serializers.CharField(required=True)
    company_size = serializers.CharField(required=True)

    class Meta:
        model = CallRequest
        fields = (
            "id",
            "name",
            "phone",
            "company_name",
            "company_size",
            "call_type",
            "scheduled_at",
            "timezone",
        )

    def validate(self, data):
        if data["call_type"] == CallRequest.CALL_SCHEDULE:
            if not data.get("scheduled_at"):
                raise serializers.ValidationError(
                    {"scheduled_at": "This field is required for scheduled calls."}
                )
        return data


class MeetingBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingBooking
        fields = "__all__"
