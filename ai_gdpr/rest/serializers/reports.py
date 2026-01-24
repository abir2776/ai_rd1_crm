from rest_framework import serializers

from ai_gdpr.models import GDPREmailTracker


class GDPRReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GDPREmailTracker
        fields = "__all__"
