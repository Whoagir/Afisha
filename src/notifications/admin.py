from django.contrib import admin

from notifications.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "type", "created_at", "is_sent", "sent_at")
    list_filter = ("type", "is_sent", "created_at")
    search_fields = ("user__username", "event__title", "message")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
