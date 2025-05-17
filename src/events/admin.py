from django.contrib import admin

from events.models import Event, Rating, Tag


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "city", "status", "seats", "organizer")
    list_filter = ("status", "city", "start_at")
    search_fields = ("title", "description", "organizer__username")
    date_hierarchy = "start_at"
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("tags",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "start_at",
                    "city",
                    "seats",
                    "status",
                    "organizer",
                )
            },
        ),
        ("Дополнительно", {"fields": ("tags", "created_at", "updated_at")}),
    )


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("user__username", "event__title", "comment")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
