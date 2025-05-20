# events/admin.py
from django import forms
from django.contrib import admin
from django.core.validators import MinValueValidator

from events.models import Event, Rating, Tag


class EventForm(forms.ModelForm):
    seats = forms.IntegerField(
        validators=[MinValueValidator(1)], help_text="Минимальное количество мест: 1"
    )

    class Meta:
        model = Event
        fields = "__all__"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventForm
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
