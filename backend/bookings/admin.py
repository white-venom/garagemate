from django.contrib import admin

from .models import Booking, Mechanic, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_min", "price_max", "duration_minutes", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"code": ["name"]}


@admin.register(Mechanic)
class MechanicAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "speciality", "experience_years", "is_active"]
    list_editable = ["is_active"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "customer_name", "service", "scheduled_date", "time_slot", "mechanic", "status"]
    list_filter = ["status", "scheduled_date", "service_mode", "service"]
    search_fields = ["reference", "customer_name", "phone", "registration_number"]
    raw_id_fields = ["conversation", "diagnosis"]
    readonly_fields = ["reference", "created_at", "updated_at"]
    date_hierarchy = "scheduled_date"
