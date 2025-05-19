# events/filters.py
import django_filters
from django.db.models import Avg, Count, F, Q

from events.models import Event, Tag


class EventFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr="iexact")
    start_date_from = django_filters.DateTimeFilter(
        field_name="start_at", lookup_expr="gte"
    )
    start_date_to = django_filters.DateTimeFilter(
        field_name="start_at", lookup_expr="lte"
    )
    has_seats = django_filters.BooleanFilter(method="filter_has_seats")
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name="tags__slug", to_field_name="slug", queryset=Tag.objects.all()
    )
    search = django_filters.CharFilter(method="filter_search")
    min_rating = django_filters.NumberFilter(method="filter_min_rating")
    organizer = django_filters.CharFilter(
        field_name="organizer__username", lookup_expr="iexact"
    )

    ordering = django_filters.OrderingFilter(
        fields=(
            ("start_at", "start_at"),
            ("-start_at", "-start_at"),
            ("created_at", "created_at"),
            ("average_rating", "average_rating"),
        ),
        field_labels={
            "start_at": "Дата начала (по возрастанию)",
            "-start_at": "Дата начала (по убыванию)",
            "created_at": "Дата создания",
            "average_rating": "Рейтинг",
        },
    )

    class Meta:
        model = Event
        fields = ["city", "status", "tags"]

    def filter_has_seats(self, queryset, name, value):
        if value:
            # Аннотируем количество активных бронирований
            queryset = queryset.annotate(
                active_bookings_count=Count(
                    "bookings", filter=Q(bookings__cancelled_at__isnull=True)
                )
            )
            # Фильтруем события, где есть свободные места
            return queryset.filter(seats__gt=F("active_bookings_count"))
        return queryset

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        # Используем полнотекстовый поиск по title и description
        return queryset.filter(search_vector=value)

    def filter_min_rating(self, queryset, name, value):
        if not value:
            return queryset

        # Аннотируем среднюю оценку и фильтруем
        return queryset.annotate(avg_rating=Avg("ratings__score")).filter(
            avg_rating__gte=value
        )
