from django.db import transaction
from rest_framework import serializers

from interview.models import (
    AIMessageConfig,
    PrimaryQuestion,
    QuestionMessageConfigConnection,
)
from interview.rest.serializers.common import PrimaryQuestionSerializer
from organizations.models import OrganizationPlatform, Platform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer
from phone_number.models import TwilioPhoneNumber
from phone_number.rest.serializers.phone_numbers import PhoneNumberSerializer


class AIPMessageConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)
    phone_uid = serializers.CharField(write_only=True)
    phone = PhoneNumberSerializer(read_only=True)
    primary_question_inputs = serializers.ListField(
        child=serializers.CharField(max_length=50), write_only=True
    )
    primary_questions = serializers.SerializerMethodField()
    platform = MyPlatformSerializer(read_only=True)

    class Meta:
        model = AIMessageConfig
        fields = [
            "uid",
            "platform",
            "phone_uid",
            "phone",
            "application_status_for_sms",
            "jobad_status_for_sms",
            "sms_time_after_status_update",
            "status_for_unsuccessful_sms",
            "status_for_successful_sms",
            "status_when_sms_is_send",
            "platform_uid",
            "primary_question_inputs",
            "primary_questions",
            "type",
        ]
        read_only_fields = ["uid", "platform"]

    def get_primary_questions(self, obj):
        question_ids = QuestionMessageConfigConnection.objects.filter(
            config=obj
        ).values_list("question_id", flat=True)
        questions = PrimaryQuestion.objects.filter(id__in=question_ids)
        return PrimaryQuestionSerializer(questions, many=True).data

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        organization = user.get_organization()

        platform_uid = validated_data.pop("platform_uid")
        phone_uid = validated_data.pop("phone_uid")
        primary_question_uids = validated_data.pop("primary_question_inputs", [])

        platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
        phone = TwilioPhoneNumber.objects.filter(uid=phone_uid).first()

        if not platform:
            raise serializers.ValidationError({"platform_uid": "Invalid platform UID"})
        if not phone:
            raise serializers.ValidationError({"phone_uid": "Invalid Phone UID"})

        questions = list(PrimaryQuestion.objects.filter(uid__in=primary_question_uids))
        if len(questions) != len(primary_question_uids):
            raise serializers.ValidationError(
                {"primary_question_inputs": "Some question UIDs are invalid."}
            )

        config = AIMessageConfig.objects.filter(organization=organization)
        if config.exists():
            raise serializers.ValidationError(
                {"details": "Message configuration already exists."}
            )

        config = AIMessageConfig.objects.create(
            organization=organization, platform=platform, phone=phone, **validated_data
        )

        connections = [
            QuestionMessageConfigConnection(question=q, config=config)
            for q in questions
        ]
        QuestionMessageConfigConnection.objects.bulk_create(connections)

        return config

    @transaction.atomic
    def update(self, instance, validated_data):
        platform_uid = validated_data.pop("platform_uid", None)
        phone_uid = validated_data.pop("phone_uid", None)
        primary_question_uids = validated_data.pop("primary_question_inputs", None)

        if platform_uid:
            platform = OrganizationPlatform.objects.filter(uid=platform_uid).first()
            if not platform:
                raise serializers.ValidationError(
                    {"platform_uid": "Invalid platform UID"}
                )
            instance.platform = platform

        if phone_uid:
            phone = TwilioPhoneNumber.objects.filter(uid=phone_uid).first()
            if not phone:
                raise serializers.ValidationError({"phone_uid": "Invalid phone UID"})
            instance.phone = phone  # Fixed: was instance.platform = phone

        if primary_question_uids is not None:
            questions = list(
                PrimaryQuestion.objects.filter(uid__in=primary_question_uids)
            )
            if len(questions) != len(primary_question_uids):
                raise serializers.ValidationError(
                    {"primary_question_inputs": "Some question UIDs are invalid."}
                )
            QuestionMessageConfigConnection.objects.filter(config=instance).delete()
            new_connections = [
                QuestionMessageConfigConnection(question=q, config=instance)
                for q in questions
            ]
            QuestionMessageConfigConnection.objects.bulk_create(new_connections)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
