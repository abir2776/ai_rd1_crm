from rest_framework import serializers

from ai_gdpr.models import GDPREmailConfig


class GDPREmailConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GDPREmailConfig
        fields = [
            "uid",
            "platform",
            "should_use_last_application_date",
            "should_use_last_placement_date",
            "should_use_last_note_creatation_date",
            "should_use_activity_creation_date",
            "should_use_candidate_update_date",
            "interval_from_last_action",
        ]
        read_only_fields = ["uid"]
