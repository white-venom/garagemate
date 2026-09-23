from django.contrib import admin

from .models import Car, Customer


class CarInline(admin.TabularInline):
    model = Car
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "city", "client_id", "created_at"]
    search_fields = ["name", "phone", "client_id"]
    inlines = [CarInline]
