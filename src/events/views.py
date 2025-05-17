from datetime import timedelta  # noqa: F401

import django_filters
from django.db.models import Avg, Count, Prefetch, Q  # noqa: F401
from django.utils import timezone
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.models import Booking  # noqa: F401
from events.filters import EventFilter
from events.models import Event, Rating, Tag
from events.permissions import IsOrganizerOrReadOnly
from events.serializers import (
    EventCreateUpdateSerializer,
    EventDetailSerializer,
    EventListSerializer,
    RatingSerializer,
    TagSerializer,
)
from events.services.booking import (
    BookingNotFound,
    EventFinished,
    EventNotFound,
    NoSeats,
    cancel_booking,
    create_booking,
)
from events.services.rating import EventNotRatable, UserNotAttended, rate_event


class EventViewSet(viewsets.ModelViewSet):
    """
    API для работы с мероприятиями.

    list:
        Получить список всех мероприятий
    retrieve:
        Получить детальную информацию о мероприятии
    create:
        Создать новое мероприятие
    update:
        Обновить мероприятие (только для организатора)
    partial_update:
        Частично обновить мероприятие (только для организатора)
    destroy:
        Удалить мероприятие (только для организатора и только в течение часа после создания)
    book:
        Забронировать место на мероприятии
    cancel_booking:
        Отменить бронирование
    my_upcoming:
        Получить список предстоящих мероприятий пользователя
    rate:
        Оценить мероприятие (только для завершенных мероприятий и только для участников)
    """

    queryset = Event.objects.all()
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        django_filters.rest_framework.DjangoFilterBackend,
    ]
    filterset_class = EventFilter
    ordering_fields = ["start_at", "created_at", "average_rating"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        queryset = Event.objects.all().select_related("organizer")

        # Аннотируем количество активных бронирований
        queryset = queryset.annotate(
            active_bookings_count=Count(
                "bookings", filter=Q(bookings__cancelled_at__isnull=True)
            ),
            average_rating=Avg("ratings__score"),
        )

        # Сортировка: сначала предстоящие, затем прошедшие и отмененные
        now = timezone.now()
        if self.action == "list" and not self.request.query_params.get("ordering"):
            upcoming = queryset.filter(
                status=Event.Status.EXPECTED, start_at__gt=now
            ).order_by("start_at")

            past_or_cancelled = queryset.filter(
                Q(status__in=[Event.Status.FINISHED, Event.Status.CANCELLED])
                | Q(start_at__lte=now)
            ).order_by("-start_at")

            # Объединяем результаты
            return upcoming.union(past_or_cancelled)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return EventListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return EventCreateUpdateSerializer
        elif self.action == "rate":
            return RatingSerializer
        return EventDetailSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsOrganizerOrReadOnly()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def perform_destroy(self, instance):
        # Проверка: можно удалить только в течение часа после создания
        if not instance.can_be_deleted():
            return Response(
                {"detail": "Events can only be deleted within 1 hour of creation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def book(self, request, pk=None):
        """Забронировать место на мероприятии"""
        try:
            booking = create_booking(request.user, pk)  # noqa: F841
            return Response(status=status.HTTP_201_CREATED)
        except NoSeats:
            return Response(
                {"detail": "No seats available for this event."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except EventNotFound:
            return Response(
                {"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except EventFinished:
            return Response(
                {"detail": "Event is already finished or cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def cancel_booking(self, request, pk=None):
        """Отменить бронирование"""
        try:
            cancel_booking(request.user, pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BookingNotFound:
            return Response(
                {"detail": "Booking not found or already cancelled."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["get"])
    def my_upcoming(self, request):
        """Получить список предстоящих мероприятий пользователя"""
        now = timezone.now()
        events = Event.objects.filter(
            bookings__user=request.user,
            bookings__cancelled_at__isnull=True,
            start_at__gt=now,
        ).order_by("start_at")

        page = self.paginate_queryset(events)
        if page is not None:
            serializer = EventListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = EventListSerializer(
            events, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        """Оценить мероприятие"""
        event = self.get_object()
        serializer = RatingSerializer(
            data=request.data, context={"request": request, "event": event}
        )

        if serializer.is_valid():
            try:
                rating = rate_event(
                    user=request.user,
                    event_id=pk,
                    score=serializer.validated_data["score"],
                    comment=serializer.validated_data.get("comment", ""),
                )
                return Response(
                    RatingSerializer(rating, context={"request": request}).data,
                    status=status.HTTP_201_CREATED,
                )
            except EventNotRatable:
                return Response(
                    {"detail": "You can only rate finished events."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except UserNotAttended:
                return Response(
                    {"detail": "You did not attend this event."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для работы с тегами.

    list:
        Получить список всех тегов
    retrieve:
        Получить детальную информацию о теге
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]


class RatingViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    API для работы с оценками.

    list:
        Получить список всех оценок
    retrieve:
        Получить детальную информацию об оценке
    """

    queryset = Rating.objects.all().select_related("user", "event")
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset
