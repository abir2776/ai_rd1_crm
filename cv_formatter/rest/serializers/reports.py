from rest_framework import serializers

from cv_formatter.models import FormattedCV


class ReportsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormattedCV
        fields = "__all__"
