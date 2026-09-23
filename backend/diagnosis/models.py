from django.db import models


class Diagnosis(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low - fix when convenient"
        MEDIUM = "medium", "Medium - get it checked soon"
        HIGH = "high", "High - avoid driving until checked"
        CRITICAL = "critical", "Critical - stop driving"

    class Source(models.TextChoices):
        RULES = "rules", "Rule engine"
        AI = "ai", "Rule engine + Gemini"

    conversation = models.ForeignKey("chat.Conversation", on_delete=models.CASCADE, related_name="diagnoses")
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=150)
    summary = models.TextField()
    # [{"name": "Worn brake pads", "likelihood": 0.62}, ...] - highest first
    probable_causes = models.JSONField(default=list)
    recommended_service = models.ForeignKey(
        "bookings.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="diagnoses"
    )
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    safe_to_drive = models.BooleanField(default=True)
    advice = models.TextField(blank=True)
    # copied from the service at the time of diagnosis so old records don't change with prices
    estimated_cost_min = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost_max = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.RULES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "diagnoses"

    def __str__(self):
        return f"{self.title} ({self.get_severity_display()})"
