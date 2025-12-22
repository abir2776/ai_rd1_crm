# models.py
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from organizations.models import Organization, OrganizationPlatform


class AISkillSearchConfig(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="ai_skill_search_config"
    )
    platform = models.ForeignKey(OrganizationPlatform, on_delete=models.CASCADE)
    search_radius_km = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        help_text="Radius in kilometers to search for candidates from job location",
    )
    candidate_status_ids = models.JSONField(
        default=list,
        help_text="List of candidate status IDs to include in search (e.g., active, inactive, archived)",
    )
    jobad_status_for_skill_search = models.CharField(
        max_length=50, default="Live", help_text="Job ad status to trigger skill search"
    )
    minimum_skill_match_percentage = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum percentage of skills that must match",
    )
    consider_employment_history = models.BooleanField(
        default=True,
        help_text="Whether to consider employment history in skill matching",
    )
    process_cv_for_skills = models.BooleanField(
        default=True,
        help_text="Extract skills from CV using AI if candidate has no skills listed",
    )
    max_candidates_per_job = models.IntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        help_text="Maximum number of candidates to return per job",
    )
    auto_apply_matched_candidates = models.BooleanField(
        default=True,
        help_text="Automatically create applications for matched candidates",
    )
    auto_apply_status_name = models.CharField(
        max_length=100,
        default="AI Available Candidate",
        help_text="Status name to set for auto-applied candidates",
    )
    send_whatsapp_notifications = models.BooleanField(
        default=True, help_text="Send WhatsApp messages to matched candidates"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable AI skill search for this organization",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_skill_search_config"
        verbose_name = "AI Skill Search Configuration"
        verbose_name_plural = "AI Skill Search Configurations"

    def __str__(self):
        return f"AI Skill Search Config - {self.organization.name}"


class JobSkillCache(models.Model):
    job_ad_id = models.IntegerField(unique=True, db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="job_skill_caches"
    )

    job_title = models.CharField(max_length=255)
    job_location = models.CharField(max_length=255)
    job_location_city = models.CharField(max_length=100)
    required_skills = models.JSONField(
        default=list, help_text="List of skills extracted by AI from job description"
    )
    nearby_cities = models.JSONField(
        default=list, help_text="List of cities within search radius"
    )
    job_description = models.JSONField(
        default=dict, help_text="Job description data used for skill extraction"
    )
    processed_at = models.DateTimeField(auto_now_add=True)
    last_matched_at = models.DateTimeField(null=True, blank=True)
    total_candidates_matched = models.IntegerField(default=0)

    is_processed = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "job_skill_cache"
        verbose_name = "Job Skill Cache"
        verbose_name_plural = "Job Skill Caches"
        ordering = ["-processed_at"]

    def __str__(self):
        return f"Job {self.job_ad_id} - {self.job_title}"


class CandidateSkillMatch(models.Model):
    candidate_id = models.IntegerField(db_index=True)
    job_ad_id = models.IntegerField(db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="candidate_skill_matches"
    )
    matched_skills = models.JSONField(
        default=list, help_text="Skills that matched between candidate and job"
    )
    match_percentage = models.FloatField(
        default=0.0, help_text="Percentage of required skills matched"
    )
    match_source = models.CharField(
        max_length=50,
        choices=[
            ("direct_skills", "Direct Skills"),
            ("employment_history", "Employment History"),
            ("cv_extraction", "CV Extraction"),
        ],
        help_text="Source of the skill match",
    )
    application_created = models.BooleanField(default=False)
    application_id = models.IntegerField(null=True, blank=True)
    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "candidate_skill_match"
        verbose_name = "Candidate Skill Match"
        verbose_name_plural = "Candidate Skill Matches"
        unique_together = ["candidate_id", "job_ad_id"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Candidate {self.candidate_id} - Job {self.job_ad_id} ({self.match_percentage}%)"
