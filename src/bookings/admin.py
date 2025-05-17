from django.contrib import admin

from bookings.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at", "cancelled_at", "is_active")
    list_filter = ("created_at", "cancelled_at")
    search_fields = ("user__username", "event__title")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    @admin.display(description="Активно", boolean=True)
    def is_active(self, obj):
        return obj.cancelled_at is None
