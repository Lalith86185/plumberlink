from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Booking, CustomerProfile, Earning, Locality, PlatformSettings, ProviderProfile,
    ProviderService, QRCode, Review, Service, ServiceCategory,
)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "booking_count", "created_at")
    search_fields = ("user__username", "user__first_name", "phone")

    def booking_count(self, obj):
        return obj.user.customer_bookings.count()
    booking_count.short_description = "Bookings"


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "active", "provider_count")
    list_filter = ("city", "active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def provider_count(self, obj):
        return obj.providers.filter(is_approved=True).count()


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "active", "sort_order")
    list_editable = ("active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "active", "sort_order")
    list_filter = ("category", "active")
    list_editable = ("active", "sort_order")
    search_fields = ("name",)


class ProviderServiceInline(admin.TabularInline):
    model = ProviderService
    extra = 0


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "phone", "listed_badge", "is_featured",
                    "rating_avg", "rating_count", "is_demo", "created_at")
    list_filter = ("is_approved", "is_available", "is_featured", "is_demo", "emergency_available")
    search_fields = ("display_name", "phone", "user__username")
    inlines = [ProviderServiceInline]
    filter_horizontal = ("areas",)
    actions = ["approve", "reject", "feature", "unfeature", "mark_demo", "unmark_demo"]

    def listed_badge(self, obj):
        if obj.is_listed:
            return format_html('<b style="color:green">● Listed</b>')
        return format_html('<b style="color:#a00">● Hidden</b>')
    listed_badge.short_description = "Status"

    def approve(self, request, queryset):
        queryset.update(is_approved=True)
    approve.short_description = "Approve selected providers"

    def reject(self, request, queryset):
        queryset.update(is_approved=False)
    reject.short_description = "Reject / hide selected providers"

    def feature(self, request, queryset):
        queryset.update(is_featured=True)
    feature.short_description = "Mark as featured"

    def unfeature(self, request, queryset):
        queryset.update(is_featured=False)
    unfeature.short_description = "Remove featured flag"

    def mark_demo(self, request, queryset):
        queryset.update(is_demo=True)
    mark_demo.short_description = "Mark as demo data"

    def unmark_demo(self, request, queryset):
        queryset.update(is_demo=False)
    unmark_demo.short_description = "Unmark demo data"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("ref_code", "customer_name", "provider", "service", "status",
                    "preferred_date", "is_demo", "created_at")
    list_filter = ("status", "is_demo", "created_at")
    search_fields = ("ref_code", "customer_name", "customer_phone", "provider__display_name")
    readonly_fields = ("ref_code", "review_token", "created_at", "updated_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("provider", "rating", "customer_name", "is_demo", "created_at")
    list_filter = ("rating", "is_demo")
    search_fields = ("provider__display_name", "customer_name", "comment")
    actions = ["mark_demo", "unmark_demo"]

    def mark_demo(self, request, queryset):
        queryset.update(is_demo=True)
    mark_demo.short_description = "Mark as demo data"

    def unmark_demo(self, request, queryset):
        queryset.update(is_demo=False)
    unmark_demo.short_description = "Unmark demo data"


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "venue_type", "locality", "scans", "is_active", "is_demo")
    list_filter = ("venue_type", "is_active", "is_demo")
    search_fields = ("name", "slug")
    readonly_fields = ("scans",)


@admin.register(Earning)
class EarningAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "kind", "amount", "booking", "note")
    list_filter = ("kind",)
    search_fields = ("provider__display_name", "note")


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("revenue_model", "lead_fee_amount", "commission_percent",
                    "subscription_monthly", "currency")
