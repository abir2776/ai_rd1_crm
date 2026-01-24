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
    logo = models.FileField(null=True, blank=True, upload_to="organizations/logo")
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
    attachment_id = models.CharField(max_length=255, db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="formatted_cvs"
    )
    candidate_id = models.IntegerField()

    pdf_file_with_logo = models.FileField(upload_to="formatted_cv")
    pdf_file_without_logo = models.FileField(upload_to="formatted_cv")

    extracted_data = models.JSONField(
        default=dict, help_text="Extracted CV data from AI"
    )

    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["attachment_id", "organization"]

    def __str__(self):
        return f"CV {self.attachment_id} - {self.organization.id}"
