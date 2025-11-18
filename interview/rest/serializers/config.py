import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers

from interview.models import (
    AIPhoneCallConfig,
    PrimaryQuestion,
    QuestionConfigConnection,
)
from organizations.models import OrganizationPlatform, Platform
from organizations.rest.serializers.organization_platform import MyPlatformSerializer
from phone_number.models import TwilioPhoneNumber
from phone_number.rest.serializers.phone_numbers import PhoneNumberSerializer


class PrimaryQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrimaryQuestion
        fields = "__all__"


class AIPhoneCallConfigSerializer(serializers.ModelSerializer):
    platform_uid = serializers.CharField(write_only=True)
    phone_uid = serializers.CharField(write_only=True)
    phone = PhoneNumberSerializer(read_only=True)
    primary_question_inputs = serializers.ListField(
        child=serializers.CharField(max_length=50), write_only=True
    )
    primary_questions = serializers.SerializerMethodField()
    platform = MyPlatformSerializer(read_only=True)

    class Meta:
        model = AIPhoneCallConfig
        fields = [
            "uid",
            "platform",
            "phone_uid",
            "phone",
            "end_call_if_primary_answer_negative",
            "application_status_for_calling",
            "jobad_status_for_calling",
            "calling_time_after_status_update",
            "status_for_unsuccessful_call",
            "status_for_successful_call",
            "status_when_call_is_placed",
            "platform_uid",
            "primary_question_inputs",
            "primary_questions",
            "welcome_message",
            "welcome_message_audio",
        ]
        read_only_fields = ["uid", "platform", "welcome_message_audio"]

    def get_primary_questions(self, obj):
        question_ids = QuestionConfigConnection.objects.filter(config=obj).values_list(
            "question_id", flat=True
        )
        questions = PrimaryQuestion.objects.filter(id__in=question_ids)
        return PrimaryQuestionSerializer(questions, many=True).data

    def convert_text_to_audio(self, text, voice_id):
        """Convert text to audio using ElevenLabs API"""
        ELEVENLABS_API_KEY = settings.ELEVENLABS_API_KEY

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY,
        }

        data = {
            "text": text,
            "model_id": "eleven_flash_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            raise serializers.ValidationError(
                {"welcome_message": f"Failed to generate audio: {str(e)}"}
            )

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        organization = user.get_organization()

        platform_uid = validated_data.pop("platform_uid")
        phone_uid = validated_data.pop("phone_uid")
        voice_id = validated_data.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        primary_question_uids = validated_data.pop("primary_question_inputs", [])
        welcome_message = validated_data.get("welcome_message")

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

        config = AIPhoneCallConfig.objects.filter(organization=organization)
        if config.exists():
            raise serializers.ValidationError(
                {"details": "Call configuration already exists."}
            )

        config = AIPhoneCallConfig.objects.create(
            organization=organization, platform=platform, phone=phone, **validated_data
        )

        # Convert welcome message to audio and save
        if welcome_message:
            audio_content = self.convert_text_to_audio(welcome_message, voice_id)
            config.welcome_message_audio.save(
                f"welcome_message_{config.uid}.mp3",
                ContentFile(audio_content),
                save=True,
            )

        connections = [
            QuestionConfigConnection(question=q, config=config) for q in questions
        ]
        QuestionConfigConnection.objects.bulk_create(connections)

        return config

    @transaction.atomic
    def update(self, instance, validated_data):
        platform_uid = validated_data.pop("platform_uid", None)
        phone_uid = validated_data.pop("phone_uid", None)
        primary_question_uids = validated_data.pop("primary_question_inputs", None)
        welcome_message = validated_data.get("welcome_message")

        if platform_uid:
            platform = Platform.objects.filter(uid=platform_uid).first()
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
            QuestionConfigConnection.objects.filter(config=instance).delete()
            new_connections = [
                QuestionConfigConnection(question=q, config=instance) for q in questions
            ]
            QuestionConfigConnection.objects.bulk_create(new_connections)

        # Update welcome message audio if message changed
        if welcome_message and welcome_message != instance.welcome_message:
            audio_content = self.convert_text_to_audio(welcome_message)
            # Delete old audio file if exists
            if instance.welcome_message_audio:
                instance.welcome_message_audio.delete(save=False)
            # Save new audio
            instance.welcome_message_audio.save(
                f"welcome_message_{instance.uid}.mp3",
                ContentFile(audio_content),
                save=False,
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
