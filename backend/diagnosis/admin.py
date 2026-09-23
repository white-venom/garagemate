from django.contrib import admin

from .models import Diagnosis


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "severity", "safe_to_drive", "source", "created_at"]
    list_filter = ["category", "severity", "source"]
    search_fields = ["title", "summary"]
    raw_id_fields = ["conversation"]
