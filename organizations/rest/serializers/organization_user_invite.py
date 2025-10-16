from rest_framework import serializers
from organizations.models import OrganizationUserInvitation
from common.tasks import send_email_task


class OrganizationUserInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationUserInvitation
        fields = [
            "id",
            "organization",
            "sender",
            "role",
            "email",
        ]
        read_only_fields = [
            "id",
            "organization",
            "sender",
        ]

    def create(self, validated_data):
        request_user = self.context["request"].user
        email = validated_data.get("email")
        organization = request_user.get_organization()
        invitation = OrganizationUserInvitation.objects.create(
            sender=request_user, organization=organization, email=email
        )
        context = {
            "organization_name": organization.name,
            "invite_link": f"http://example.com/invite/{invitation.token}",
            "current_year": 2025,
        }
        send_email_task.delay(
            subject="You're invited to join our organization",
            recipient=email,
            template_name="organization_invites/invite.html",
            context=context,
        )
        return invitation
