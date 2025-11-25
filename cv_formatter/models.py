from django.contrib.postgres.fields import ArrayField
from django.db import models

from organizations.models import Organization


class CVFormatterConfig(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="cv_formatter_config"
    )
    platform = models.ForeignKey(
        "organizations.OrganizationPlatform",
        on_delete=models.CASCADE,
        help_text="Recruitment platform (e.g., JobAdder)",
    )
    job_status_for_formatting = models.CharField(
        max_length=50,
        default="Current",
        help_text="Only format CVs from jobs in this status",
    )
    enabled_sections = ArrayField(
        models.CharField(max_length=50),
        default=[
            "Full Name",
            "Email Address",
            "Phone Number",
            "Address",
            "Professional Summary",
            "Professional Experience",
            "Education",
            "Skills",
            "Certifications",
            "Languages",
            "Areas of Expertise",
            "Areas for improvement & recommendations",
        ],
        help_text="List of CV sections to extract",
    )

    upload_with_logo = models.BooleanField(
        default=True, help_text="Upload formatted CV with company logo"
    )
    upload_without_logo = models.BooleanField(
        default=True, help_text="Upload formatted CV without company logo"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cv_formatter_config"
        verbose_name = "CV Formatter Configuration"
        verbose_name_plural = "CV Formatter Configurations"
        unique_together = ("organization", "platform")

    def __str__(self):
        return f"CV Formatter Config - {self.organization.name}"

    def get_enabled_sections(self):
        """
        Returns list of enabled sections, defaults to all if not set.
        """
        if not self.enabled_sections:
            return [
                "full_name",
                "email",
                "phone",
                "address",
                "professional_summary",
                "professional_experience",
                "education",
                "skills",
                "certifications",
                "languages",
                "areas_of_expertise",
                "recommendations",
            ]
        return self.enabled_sections


class FormattedCV(models.Model):
    STATUS_CHOICES = [
        ("success", "Success"),
        ("download_failed", "Download Failed"),
        ("extraction_failed", "Text Extraction Failed"),
        ("parsing_failed", "Parsing Failed"),
        ("ai_failed", "AI Processing Failed"),
        ("pdf_generation_failed", "PDF Generation Failed"),
        ("upload_failed", "Upload Failed"),
    ]

    attachment_id = models.CharField(max_length=255, db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="formatted_cvs"
    )
    candidate_id = models.IntegerField()

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="success")

    extracted_data = models.JSONField(
        default=dict, help_text="Extracted CV data from AI"
    )

    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "formatted_cvs"
        verbose_name = "Formatted CV"
        verbose_name_plural = "Formatted CVs"
        unique_together = ["attachment_id", "organization"]
        indexes = [
            models.Index(fields=["attachment_id", "organization"]),
            models.Index(fields=["candidate_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"CV {self.attachment_id} - {self.status}"

    def is_successful(self):
        return self.status == "success"


class CVSection(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(
        default=False, help_text="If true, this section cannot be disabled"
    )
    order = models.IntegerField(default=0)

    class Meta:
        db_table = "cv_sections"
        verbose_name = "CV Section"
        verbose_name_plural = "CV Sections"
        ordering = ["order", "display_name"]

    def __str__(self):
        return self.display_name


class CVFormattingLog(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="cv_formatting_logs"
    )
    attachment_id = models.CharField(max_length=255)
    candidate_id = models.IntegerField()
    candidate_name = models.CharField(max_length=255)

    stage = models.CharField(
        max_length=50,
        choices=[
            ("download", "Download"),
            ("extraction", "Text Extraction"),
            ("ai_processing", "AI Processing"),
            ("pdf_generation", "PDF Generation"),
            ("upload", "Upload"),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("started", "Started"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
    )

    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cv_formatting_logs"
        verbose_name = "CV Formatting Log"
        verbose_name_plural = "CV Formatting Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["attachment_id"]),
            models.Index(fields=["candidate_id"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"{self.stage} - {self.status} - {self.candidate_name}"
