# events/views.py
import django_filters
from rest_framework import filters, mixins, permissions, status, viewsets  # noqa: F401
from rest_framework.decorators import action
from rest_framework.response import Response

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
from events.services.event import get_events_queryset  # noqa: F401
from events.services.event import (
    can_delete_event,
    get_user_upcoming_events,
)
from events.services.rating import EventNotFound as RatingEventNotFound
from events.services.rating import EventNotRatable, UserNotAttended, rate_event


class EventViewSet(viewsets.ModelViewSet):
    """
    API для работы с мероприятиями.
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
        if not can_delete_event(instance):
            return Response(
                {"detail": "Events can only be deleted within 1 hour of creation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def book(self, request, pk=None):
        """Забронировать место на мероприятии"""
        try:
            booking = create_booking(request.user, pk)
            return Response(
                {"status": "booking created", "booking_id": booking.id},
                status=status.HTTP_201_CREATED,
            )
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
            booking = cancel_booking(request.user, pk)
            return Response(
                {"status": "booking cancelled", "booking_id": booking.id},
                status=status.HTTP_200_OK,
            )
        except BookingNotFound:
            return Response(
                {"detail": "Booking not found or already cancelled."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["get"])
    def my_upcoming(self, request):
        """Получить список предстоящих мероприятий пользователя"""
        # Добавляем select_related для связанных моделей
        events = (
            get_user_upcoming_events(request.user)
            .select_related("organizer")
            .prefetch_related("tags")
        )

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
            except (EventNotRatable, RatingEventNotFound):
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


class RatingViewSet(viewsets.ModelViewSet):
    """
    API для работы с оценками мероприятий.
    """

    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Оптимизируем запрос с select_related
        return (
            Rating.objects.filter(event__organizer=self.request.user)
            | Rating.objects.filter(user=self.request.user)
        ).select_related("user", "event", "event__organizer")

    def perform_create(self, serializer):
        event_id = self.request.data.get("event")
        try:
            rating = rate_event(
                user=self.request.user,
                event_id=event_id,
                score=serializer.validated_data["score"],
                comment=serializer.validated_data.get("comment", ""),
            )
            return rating
        except (EventNotRatable, EventNotFound):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "You can only rate finished events."})
        except UserNotAttended:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied({"detail": "You did not attend this event."})


class TagViewSet(viewsets.ModelViewSet):
    """
    API для работы с тегами мероприятий.
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Tag.objects.all().order_by("name")
