from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from common.models import BaseModelWithUID
from organizations.models import Organization, OrganizationPlatform


class LeadGenerationConfig(BaseModelWithUID):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    find_contacts_without_company = models.BooleanField(default=True)
    is_company_address_required = models.BooleanField(default=True)
    # If True, company creation requires at least one contact to be present in extracted data
    is_contacts_item_required = models.BooleanField(
        default=False,
        help_text="If True, skip companies that don't have contact information"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name}-{self.platform.platform.name}"


class LeadGenerationReport(BaseModelWithUID):
    """Stores execution reports for lead generation tasks"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("partial", "Partially Completed"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="lead_generation_reports"
    )
    config = models.ForeignKey(
        LeadGenerationConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )

    # Execution metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Summary statistics
    total_candidates_processed = models.IntegerField(default=0)
    total_candidates_failed = models.IntegerField(default=0)
    total_companies_extracted = models.IntegerField(default=0)
    total_companies_created = models.IntegerField(default=0)
    total_companies_skipped = models.IntegerField(default=0)
    total_companies_failed = models.IntegerField(default=0)
    total_contacts_extracted = models.IntegerField(default=0)
    total_contacts_created = models.IntegerField(default=0)
    total_contacts_failed = models.IntegerField(default=0)

    # Detailed tracking
    candidates_with_no_resume = models.IntegerField(default=0)
    candidates_with_no_data = models.IntegerField(default=0)
    companies_skipped_related = models.IntegerField(default=0)
    companies_skipped_no_address = models.IntegerField(default=0)
    companies_skipped_existing = models.IntegerField(default=0)
    companies_skipped_no_contact = models.IntegerField(default=0)

    # ID tracking - NEW FIELDS
    created_company_ids = ArrayField(
        models.IntegerField(), 
        default=list, 
        blank=True,
        help_text="All company IDs created during this report"
    )
    created_contact_ids = ArrayField(
        models.IntegerField(), 
        default=list, 
        blank=True,
        help_text="All contact IDs created during this report"
    )

    # Error tracking
    error_message = models.TextField(null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True, default=dict)

    # Detailed logs (optional, for debugging)
    execution_log = models.TextField(null=True, blank=True)
    candidate_ids_processed = ArrayField(
        models.IntegerField(), default=list, blank=True
    )
    candidate_ids_failed = ArrayField(models.IntegerField(), default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Report {self.uid} - {self.organization.name} - {self.status}"

    @property
    def duration_seconds(self):
        """Calculate execution duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        """Calculate success rate as percentage"""
        if self.total_candidates_processed > 0:
            successful = self.total_candidates_processed - self.total_candidates_failed
            return round((successful / self.total_candidates_processed) * 100, 2)
        return 0.0

    def add_log(self, message):
        """Append a message to execution log"""
        timestamp = timezone.now()
        log_entry = f"[{timestamp}] {message}\n"
        if self.execution_log:
            self.execution_log += log_entry
        else:
            self.execution_log = log_entry


class CandidateLeadResult(BaseModelWithUID):
    """Stores individual candidate processing results"""

    report = models.ForeignKey(
        LeadGenerationReport, on_delete=models.CASCADE, related_name="candidate_results"
    )

    candidate_id = models.IntegerField()
    candidate_name = models.CharField(max_length=255, null=True, blank=True)

    # Processing status
    processed_successfully = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)

    # Extracted data counts
    companies_extracted = models.IntegerField(default=0)
    companies_created = models.IntegerField(default=0)
    companies_skipped = models.IntegerField(default=0)
    contacts_extracted = models.IntegerField(default=0)
    contacts_created = models.IntegerField(default=0)

    # Resume details
    had_resume = models.BooleanField(default=False)
    resume_text_length = models.IntegerField(default=0)

    # Detailed results (optional)
    extracted_data = models.JSONField(null=True, blank=True, default=dict)
    created_company_ids = ArrayField(models.IntegerField(), default=list, blank=True)
    created_contact_ids = ArrayField(
        models.IntegerField(), 
        default=list, 
        blank=True,
        help_text="Contact IDs created for this candidate"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["report", "processed_successfully"]),
            models.Index(fields=["candidate_id"]),
        ]

    def __str__(self):
        return f"Result for Candidate {self.candidate_id} - {self.candidate_name}"


class MarketingAutomationConfig(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="marketing_automation_configs",
        help_text="Organization this configuration belongs to",
    )

    platform = models.ForeignKey(
        OrganizationPlatform,
        on_delete=models.CASCADE,
        related_name="marketing_automation_configs",
        help_text="Platform/ATS integration to use",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether marketing automation is active for this organization",
    )

    exclude_agencies = models.BooleanField(
        default=True,
        help_text="If True, skip companies identified as recruitment agencies",
    )

    opportunity_stage = models.CharField(
        null=True,
        blank=True,
        help_text="Stage ID to assign to created opportunities (optional)",
    )

    opportunity_owners = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text="List of user IDs who will own the created opportunities",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketing_automation_config"
        verbose_name = "Marketing Automation Config"
        verbose_name_plural = "Marketing Automation Configs"
        unique_together = ["organization", "platform"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return (
            f"Marketing Config - Org: {self.organization_id} (Active: {self.is_active})"
        )


class MarketingAutomationReport(models.Model):
    """
    Tracks the results and metrics of marketing automation runs.
    Each report represents one execution of the automation for an organization.
    """

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("partial", "Partially Completed"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="marketing_automation_reports",
        help_text="Organization this report belongs to",
    )

    config = models.ForeignKey(
        "MarketingAutomationConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        help_text="Configuration used for this automation run",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="running",
        help_text="Current status of the automation run",
    )

    started_at = models.DateTimeField(
        auto_now_add=True, help_text="When the automation started"
    )

    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the automation completed"
    )

    duration_seconds = models.IntegerField(
        null=True, blank=True, help_text="Total duration of the run in seconds"
    )

    total_companies_fetched = models.IntegerField(
        default=0, help_text="Total number of companies fetched from platform"
    )

    companies_processed = models.IntegerField(
        default=0, help_text="Number of companies that were analyzed"
    )

    companies_skipped = models.IntegerField(
        default=0,
        help_text="Number of companies skipped (no contact info, agencies, etc.)",
    )

    companies_hiring = models.IntegerField(
        default=0, help_text="Number of companies identified as actively hiring"
    )

    companies_failed = models.IntegerField(
        default=0, help_text="Number of companies that failed to process"
    )

    opportunities_created = models.IntegerField(
        default=0, help_text="Total number of opportunities created"
    )

    opportunities_failed = models.IntegerField(
        default=0, help_text="Number of opportunities that failed to create"
    )

    agencies_detected = models.IntegerField(
        default=0, help_text="Number of recruitment agencies detected"
    )

    agencies_excluded = models.IntegerField(
        default=0, help_text="Number of agencies excluded from processing"
    )

    job_titles_found = ArrayField(
        models.CharField(max_length=200),
        default=list,
        blank=True,
        help_text="All unique job titles found during this run",
    )

    companies_with_opportunities = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text="List of company IDs that had opportunities created",
    )

    skipped_no_contact = models.IntegerField(
        default=0, help_text="Companies skipped due to missing contact information"
    )

    skipped_no_hiring = models.IntegerField(
        default=0, help_text="Companies skipped as they're not hiring"
    )

    skipped_no_job_titles = models.IntegerField(
        default=0, help_text="Companies skipped due to no job titles found"
    )

    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if the run failed"
    )

    error_details = models.JSONField(
        null=True, blank=True, help_text="Detailed error information and stack traces"
    )

    ai_api_calls = models.IntegerField(
        default=0, help_text="Number of AI API calls made during this run"
    )

    platform_api_calls = models.IntegerField(
        default=0, help_text="Number of platform API calls made"
    )

    notes = models.TextField(
        blank=True, help_text="Additional notes or observations about this run"
    )

    class Meta:
        db_table = "marketing_automation_report"
        verbose_name = "Marketing Automation Report"
        verbose_name_plural = "Marketing Automation Reports"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["organization", "-started_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-started_at"]),
            models.Index(fields=["config", "-started_at"]),
        ]

    def __str__(self):
        return f"Report {self.id} - Org {self.organization_id} - {self.status} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"

    def calculate_duration(self):
        """Calculate and update the duration if completed_at is set"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
            return self.duration_seconds
        return None

    def mark_completed(self, status="completed"):
        """Mark the report as completed and calculate duration"""
        self.completed_at = timezone.now()
        self.status = status
        self.calculate_duration()
        self.save()

    def mark_failed(self, error_message, error_details=None):
        """Mark the report as failed with error information"""
        self.status = "failed"
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.error_details = error_details
        self.calculate_duration()
        self.save()

    def add_job_title(self, job_title):
        """Add a unique job title to the found list"""
        if job_title and job_title != "null" and job_title not in self.job_titles_found:
            self.job_titles_found.append(job_title)

    def add_company_with_opportunity(self, company_id):
        """Add a company ID to the list of companies with opportunities"""
        if company_id not in self.companies_with_opportunities:
            self.companies_with_opportunities.append(company_id)

    def get_success_rate(self):
        """Calculate the success rate of company processing"""
        if self.companies_processed == 0:
            return 0
        return (self.companies_hiring / self.companies_processed) * 100

    def get_opportunity_creation_rate(self):
        """Calculate the rate of successful opportunity creation"""
        total_attempts = self.opportunities_created + self.opportunities_failed
        if total_attempts == 0:
            return 0
        return (self.opportunities_created / total_attempts) * 100

    @property
    def is_complete(self):
        """Check if the report is in a completed state"""
        return self.status in ["completed", "failed", "partial"]

    @property
    def summary(self):
        """Generate a human-readable summary of the report"""
        return {
            "status": self.status,
            "duration": f"{self.duration_seconds}s"
            if self.duration_seconds
            else "In progress",
            "companies": {
                "fetched": self.total_companies_fetched,
                "processed": self.companies_processed,
                "hiring": self.companies_hiring,
                "skipped": self.companies_skipped,
                "failed": self.companies_failed,
            },
            "opportunities": {
                "created": self.opportunities_created,
                "failed": self.opportunities_failed,
            },
            "success_rate": f"{self.get_success_rate():.1f}%",
        }