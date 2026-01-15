from rest_framework import serializers

from awr_compliance.models import AWRTracker


class AWRReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AWRTracker
        fields = "__all__"
