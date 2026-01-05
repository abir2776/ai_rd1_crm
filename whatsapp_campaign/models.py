from django.db import models
from django.utils import timezone

from organizations.models import Organization, OrganizationPlatform


class WhatsAppCampaignConfig(models.Model):
    SCHEDULE_CHOICES = [
        ("now", "Send Now"),
        ("scheduled", "Schedule for Later"),
    ]

    CHATBOT_TEMPLATE_CHOICES = [
        ("ai_call", "AI Call"),
    ]

    CONTACT_FILTER_CHOICES = [
        ("all", "All Contacts"),
        ("selected", "Selected Contacts"),
    ]
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="whatsapp_campaigns"
    )
    platform = models.ForeignKey(
        OrganizationPlatform,
        on_delete=models.CASCADE,
        related_name="whatsapp_campaigns",
    )
    campaign_title = models.CharField(max_length=255)
    twilio_content_sid = models.CharField(
        max_length=255, help_text="Twilio Content Template SID"
    )
    content_variables = models.JSONField(
        default=list, help_text="List of content variables with serial and value"
    )
    contact_filter_type = models.CharField(
        max_length=20, choices=CONTACT_FILTER_CHOICES, default="all"
    )
    selected_contact_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of contact IDs from JobAdder (only used if filter_type is 'selected')",
    )
    schedule_type = models.CharField(
        max_length=20, choices=SCHEDULE_CHOICES, default="now"
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to send the campaign (only used if schedule_type is 'scheduled')",
    )
    chatbot_template = models.CharField(
        max_length=50,
        choices=CHATBOT_TEMPLATE_CHOICES,
        default="ai_call",
        help_text="Template for AI chatbot interactions",
    )
    ai_instructions = models.TextField(
        blank=True,
        help_text="Custom instructions for AI to handle responses to this campaign",
    )
    from_phone_number = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("sending", "Sending"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="draft",
    )
    total_contacts = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    messages_failed = models.IntegerField(default=0)
    messages_delivered = models.IntegerField(default=0)
    messages_read = models.IntegerField(default=0)
    responses_received = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "whatsapp_campaign_config"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["status", "schedule_type"]),
        ]

    def __str__(self):
        return f"{self.campaign_title} - {self.organization.name}"

    def get_content_variables_dict(self):
        variables_dict = {}
        for var in self.content_variables:
            serial = str(var.get("serial"))
            value = var.get("value", "")
            variables_dict[serial] = value
        return variables_dict

    def mark_as_sending(self):
        self.status = "sending"
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "updated_at"])

    def mark_as_completed(self):
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_as_failed(self):
        self.status = "failed"
        self.save(update_fields=["status", "updated_at"])

    def increment_sent(self):
        self.messages_sent += 1
        self.save(update_fields=["messages_sent", "updated_at"])

    def increment_failed(self):
        self.messages_failed += 1
        self.save(update_fields=["messages_failed", "updated_at"])

    def increment_delivered(self):
        self.messages_delivered += 1
        self.save(update_fields=["messages_delivered", "updated_at"])

    def increment_read(self):
        self.messages_read += 1
        self.save(update_fields=["messages_read", "updated_at"])

    def increment_responses(self):
        self.responses_received += 1
        self.save(update_fields=["responses_received", "updated_at"])


class WhatsAppCampaignReport(models.Model):
    MESSAGE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
        ("undelivered", "Undelivered"),
    ]
    campaign = models.ForeignKey(
        WhatsAppCampaignConfig, on_delete=models.CASCADE, related_name="reports"
    )
    contact_id = models.CharField(max_length=100, help_text="Contact ID from JobAdder")
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20)
    message_sid = models.CharField(
        max_length=255, blank=True, help_text="Twilio Message SID"
    )
    message_status = models.CharField(
        max_length=20, choices=MESSAGE_STATUS_CHOICES, default="pending"
    )
    message_content = models.TextField(
        blank=True, help_text="The actual message content sent"
    )
    error_code = models.CharField(max_length=10, blank=True)
    error_message = models.TextField(blank=True)
    conversation_json = models.JSONField(
        default=list, help_text="Complete conversation history with this contact"
    )
    has_responded = models.BooleanField(default=False)
    first_response_at = models.DateTimeField(null=True, blank=True)
    last_response_at = models.DateTimeField(null=True, blank=True)
    response_count = models.IntegerField(default=0)
    ai_conversation_active = models.BooleanField(
        default=False,
        help_text="Whether AI chatbot is actively conversing with this contact",
    )
    ai_conversation_ended_at = models.DateTimeField(null=True, blank=True)
    ai_conversation_outcome = models.CharField(
        max_length=50,
        blank=True,
        help_text="Outcome of AI conversation (e.g., 'successful', 'unsuccessful', 'abandoned')",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "whatsapp_campaign_report"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign", "message_status"]),
            models.Index(fields=["contact_id"]),
            models.Index(fields=["contact_phone"]),
            models.Index(fields=["message_sid"]),
            models.Index(fields=["has_responded"]),
        ]
        unique_together = [["campaign", "contact_id"]]

    def __str__(self):
        return f"{self.contact_name} - {self.campaign.campaign_title} - {self.message_status}"

    def update_status(self, status, error_code=None, error_message=None):
        """Update message status"""
        self.message_status = status

        if status == "sent":
            self.sent_at = timezone.now()
        elif status == "delivered":
            self.delivered_at = timezone.now()
            self.campaign.increment_delivered()
        elif status == "read":
            self.read_at = timezone.now()
            self.campaign.increment_read()
        elif status == "failed":
            self.failed_at = timezone.now()
            self.error_code = error_code or ""
            self.error_message = error_message or ""

        self.save()

    def add_message_to_conversation(self, sender, message):
        """Add a message to the conversation history"""
        conversation_entry = {
            "sender": sender,
            "message": message,
            "timestamp": timezone.now().isoformat(),
        }

        self.conversation_json.append(conversation_entry)

        if sender == "contact":
            self.response_count += 1
            self.last_response_at = timezone.now()

            if not self.has_responded:
                self.has_responded = True
                self.first_response_at = timezone.now()
                self.campaign.increment_responses()

        self.save()

    def start_ai_conversation(self):
        """Mark AI conversation as active"""
        self.ai_conversation_active = True
        self.save(update_fields=["ai_conversation_active", "updated_at"])

    def end_ai_conversation(self, outcome="completed"):
        """End AI conversation"""
        self.ai_conversation_active = False
        self.ai_conversation_ended_at = timezone.now()
        self.ai_conversation_outcome = outcome
        self.save(
            update_fields=[
                "ai_conversation_active",
                "ai_conversation_ended_at",
                "ai_conversation_outcome",
                "updated_at",
            ]
        )
