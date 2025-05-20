# events/views.py
from typing import Dict, Union

from django.db.models import Count, Q
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from events.filters import EventFilter
from events.models import Event, Rating, Tag
from events.permissions import IsOrganizerOrReadOnly
from events.serializers import (
    EventCreateUpdateSerializer,
    EventDetailSerializer,
    EventListSerializer,
    EventTagsSerializer,
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
from events.services.event import (
    can_delete_event,
)
from events.services.rating import EventNotRatable, UserNotAttended, rate_event

ERROR_RESPONSES = {
    400: {
        "type": "object",
        "properties": {
            "start_at": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["Дата начала события должна быть в будущем"],
            }
        },
    },
    401: {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "example": "Учетные данные не были предоставлены.",
            }
        },
    },
    403: {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "example": "У вас недостаточно прав для выполнения данного действия.",
            }
        },
    },
    404: {
        "type": "object",
        "properties": {"detail": {"type": "string", "example": "Страница не найдена."}},
    },
}


def get_error_response(example: dict, code: int):
    return {
        code: {
            "type": "object",
            "properties": {
                k: {"type": "string", "example": v} for k, v in example.items()
            },
        }
    }


BOOKING_400 = get_error_response({"detail": "Нет свободных мест."}, 400)
BOOKING_404 = get_error_response({"detail": "Мероприятие не найдено."}, 404)
RATING_400 = get_error_response({"detail": "Оценка только после мероприятия."}, 400)
RATING_403 = get_error_response({"detail": "Вы не были на этом мероприятие."}, 403)
TAG_400 = get_error_response({"tags": ["Необходимо указать хотя бы один тег"]}, 400)


@extend_schema_view(
    list=extend_schema(
        summary="Список мероприятий",
        description="Получить список всех мероприятий с возможностью фильтрации и сортировки.",
        parameters=[
            OpenApiParameter(
                name="city",
                description="Фильтрация по городу (точное совпадение, без учета регистра)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="start_date_from",
                description="Фильтрация по дате начала (от указанной даты)",
                required=False,
                type=OpenApiTypes.DATETIME,
            ),
            OpenApiParameter(
                name="start_date_to",
                description="Фильтрация по дате начала (до указанной даты)",
                required=False,
                type=OpenApiTypes.DATETIME,
            ),
            OpenApiParameter(
                name="has_seats",
                description="Фильтрация по наличию свободных мест (true - есть места, false - нет мест)",
                required=False,
                type=bool,
            ),
            OpenApiParameter(
                name="tags",
                description="Фильтрация по тегам (список slug-ов тегов через запятую)",
                required=False,
                type=OpenApiTypes.STR,
                explode=False,
            ),
            OpenApiParameter(
                name="search",
                description="Поисковый запрос по названию и описанию мероприятия",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="min_rating",
                description="Фильтрация по минимальному среднему рейтингу",
                required=False,
                type=float,
            ),
            OpenApiParameter(
                name="organizer",
                description="Фильтрация по имени пользователя организатора",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="status",
                description="Фильтрация по статусу мероприятия",
                required=False,
                type=str,
                enum=["expected", "cancelled", "finished"],
            ),
            OpenApiParameter(
                name="page",
                description="Номер страницы в пагинированном списке",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="ordering",
                description="Сортировка результатов",
                required=False,
                type=str,
                examples=[
                    OpenApiExample(
                        name="По возрастанию даты начала",
                        value="start_at",
                        description="Сортировка по дате начала (от старых к новым)",
                    ),
                    OpenApiExample(
                        name="По убыванию даты начала",
                        value="-start_at",
                        description="Сортировка по дате начала (от новых к старым)",
                    ),
                    OpenApiExample(
                        name="По возрастанию даты создания",
                        value="created_at",
                        description="Сортировка по дате создания события (от ранних к поздним)",
                    ),
                    OpenApiExample(
                        name="По убыванию даты создания",
                        value="-created_at",
                        description="Сортировка по дате создания события (от поздних к ранним)",
                    ),
                    OpenApiExample(
                        name="По возрастанию рейтинга",
                        value="average_rating",
                        description="Сортировка по среднему рейтингу (от низкого к высокому)",
                    ),
                    OpenApiExample(
                        name="По убыванию рейтинга",
                        value="-average_rating",
                        description="Сортировка по среднему рейтингу (от высокого к низкому)",
                    ),
                ],
            ),
        ],
        responses={
            200: EventListSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Пример ответа",
                value={
                    "count": 2,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "title": "Конференция Python разработчиков",
                            "start_at": "2025-06-15T10:00:00Z",
                            "city": "Москва",
                            "status": "expected",
                            "available_seats": 45,
                            "organizer_name": "admin",
                            "average_rating": 0,
                            "tags": [
                                {"id": 1, "name": "Python", "slug": "python"},
                                {"id": 2, "name": "IT", "slug": "it"},
                            ],
                            "is_booked": False,
                        },
                        {
                            "id": 2,
                            "title": "Мастер-класс по Django",
                            "start_at": "2025-06-20T14:00:00Z",
                            "city": "Санкт-Петербург",
                            "status": "expected",
                            "available_seats": 15,
                            "organizer_name": "user",
                            "average_rating": 4.5,
                            "tags": [
                                {"id": 1, "name": "Python", "slug": "python"},
                                {"id": 3, "name": "Django", "slug": "django"},
                            ],
                            "is_booked": True,
                        },
                    ],
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Создать мероприятие",
        description="Создание нового мероприятия. Доступно только авторизованным пользователям.",
        request=EventCreateUpdateSerializer,
        responses={
            201: EventDetailSerializer,
            **get_error_response(
                {"start_at": ["Дата начала события должна быть в будущем"]}, 400
            ),
            **get_error_response(
                {"detail": "Учетные данные не были предоставлены."}, 401
            ),
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={
                    "title": "Конференция Python разработчиков",
                    "description": "Ежегодная конференция для Python разработчиков",
                    "start_at": "2025-06-15T10:00:00Z",
                    "city": "Москва",
                    "seats": 50,
                    "status": "expected",
                    "tags": ["python", "it"],
                },
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Получить мероприятие",
        description="Получить подробную информацию о мероприятии по ID.",
        responses={
            200: EventDetailSerializer,
            **get_error_response({"detail": "Страница не найдена."}, 404),
        },
    ),
    update=extend_schema(
        summary="Обновить мероприятие",
        description="Полное обновление информации о мероприятии. Доступно только организатору.",
        request=EventCreateUpdateSerializer,
        responses={200: EventDetailSerializer, **ERROR_RESPONSES},
    ),
    partial_update=extend_schema(
        summary="Частичное обновление мероприятия",
        description="Частичное обновление информации о мероприятии. Доступно только организатору.",
        request=EventCreateUpdateSerializer,
        responses={200: EventDetailSerializer, **ERROR_RESPONSES},
    ),
    destroy=extend_schema(
        summary="Удалить мероприятие",
        description="Удаление мероприятия. Доступно только организатору и только в течение часа после создания.",
        responses={
            204: None,
            **{k: v for k, v in ERROR_RESPONSES.items() if k != 400},
            403: get_error_response(
                {"detail": "Удалить мероприятие можно только в течение 1 часа."}, 403
            ),
        },
    ),
    book=extend_schema(
        summary="Забронировать место",
        description="Бронирование места на мероприятии для текущего пользователя.",
        responses={
            201: OpenApiExample(
                "Успешное бронирование",
                value={"status": "booking created", "booking_id": 1},
                response_only=True,
            ),
            **BOOKING_400,
            **ERROR_RESPONSES[401],
            **BOOKING_404,
        },
    ),
    cancel_booking=extend_schema(
        summary="Отменить бронирование",
        description="Отмена существующего бронирования текущего пользователя на мероприятие.",
        responses={
            200: OpenApiExample(
                "Успешная отмена",
                value={"status": "booking cancelled", "booking_id": 1},
                response_only=True,
            ),
            **ERROR_RESPONSES[401],
            **get_error_response({"detail": "Бронирование не найдено."}, 404),
        },
    ),
    rate=extend_schema(
        summary="Оценить мероприятие",
        description=(
            "Оценка мероприятия пользователем. Доступно только для завершенных мероприятий, "
            "которые пользователь посетил."
        ),
        request=RatingSerializer,
        responses={
            201: RatingSerializer,
            **RATING_400,
            **ERROR_RESPONSES[401],
            **RATING_403,
            **ERROR_RESPONSES[404],
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={"score": 5, "comment": "Отличное мероприятие!"},
                request_only=True,
            )
        ],
    ),
    rating=extend_schema(
        summary="Управление оценкой мероприятия",
        description="""GET - получить средний рейтинг и количество оценок
    PUT/PATCH - создать/обновить оценку
    DELETE - удалить оценку""",
        methods=["GET", "PUT", "PATCH", "DELETE"],
        request=RatingSerializer,
        responses={
            200: RatingSerializer,
            204: None,
            400: OpenApiExample(
                "Ошибка валидации",
                value={"detail": "You can only rate finished events."},
                response_only=True,
            ),
            403: OpenApiExample(
                "Доступ запрещен",
                value={"detail": "You did not attend this event."},
                response_only=True,
            ),
            404: OpenApiExample(
                "Не найдено", value={"detail": "Not found."}, response_only=True
            ),
        },
        examples=[
            OpenApiExample(
                "Пример запроса оценки",
                value={"score": 8, "comment": "Отличное мероприятие!"},
                request_only=True,
            )
        ],
    ),
    add_tags=extend_schema(
        summary="Добавить теги",
        description="Добавление тегов к мероприятию. Доступно только организатору.",
        request=EventTagsSerializer,
        responses={
            200: EventDetailSerializer,
            **TAG_400,
            **ERROR_RESPONSES[401],
            **ERROR_RESPONSES[403],
            **ERROR_RESPONSES[404],
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={"tags": ["python", "django", "rest"]},
                request_only=True,
            )
        ],
    ),
    remove_tags=extend_schema(
        summary="Удалить теги",
        description="Удаление тегов из мероприятия. Доступно только организатору.",
        request=EventTagsSerializer,
        responses={
            200: EventDetailSerializer,
            **TAG_400,
            **ERROR_RESPONSES[401],
            **ERROR_RESPONSES[403],
            **ERROR_RESPONSES[404],
        },
        examples=[
            OpenApiExample(
                "Пример запроса", value={"tags": ["rest"]}, request_only=True
            )
        ],
    ),
    tags=extend_schema(
        summary="Список тегов мероприятия",
        description="Получение списка всех тегов, присвоенных мероприятию.",
        responses={
            200: TagSerializer(many=True),
            404: ERROR_RESPONSES[404],
        },
    ),
)
class EventViewSet(viewsets.ModelViewSet):
    """
    API для работы с мероприятиями.
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_class = EventFilter

    def get_queryset(self):
        """
        Получает оптимизированный QuerySet событий с аннотациями.
        """
        queryset = (
            Event.objects.all().select_related("organizer").prefetch_related("tags")
        )

        queryset = queryset.annotate(
            active_bookings_count=Count(
                "bookings", filter=Q(bookings__cancelled_at__isnull=True)
            ),
        )

        # Применяем базовую сортировку по умолчанию
        return queryset.order_by("status", "start_at")

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
            raise PermissionDenied(
                "Events can only be deleted within 1 hour of creation."
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
                    user=request.user, event=event, data=serializer.validated_data
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

    @action(detail=True, methods=["get", "put", "patch", "delete"])
    def rating(self, request, pk=None):
        """Управление оценкой мероприятия"""
        event = self.get_object()
        user = request.user

        if request.method == "GET":
            response_data: Dict[str, Union[float, int]] = {
                "average_rating": event.average_rating,
                "ratings_count": event.ratings_count,
            }
            return Response(response_data)

        elif request.method in ["PUT", "PATCH"]:
            serializer = RatingSerializer(
                data=request.data,
                context={"request": request, "event": event},
                partial=request.method == "PATCH",
            )

            if serializer.is_valid():
                try:
                    rating = rate_event(
                        user=user, event=event, data=serializer.validated_data
                    )
                    return Response(
                        RatingSerializer(rating).data, status=status.HTTP_200_OK
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

        elif request.method == "DELETE":
            rating = Rating.objects.filter(event=event, user=user).first()
            if not rating:
                return Response(status=status.HTTP_404_NOT_FOUND)
            rating.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsOrganizerOrReadOnly],
    )
    def add_tags(self, request, pk=None):
        """Добавить теги к мероприятию"""
        event = self.get_object()
        serializer = EventTagsSerializer(data=request.data)

        if serializer.is_valid():
            current_tags = set(event.tags.all())
            new_tags = set(serializer.validated_data["tags"])
            tags_to_add = new_tags - current_tags

            if tags_to_add:
                event.tags.add(*tags_to_add)

            return Response(
                EventDetailSerializer(event, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsOrganizerOrReadOnly],
    )
    def remove_tags(self, request, pk=None):
        """Удалить теги из мероприятия"""
        event = self.get_object()
        serializer = EventTagsSerializer(data=request.data)

        if serializer.is_valid():
            tags_to_remove = serializer.validated_data["tags"]
            event.tags.remove(*tags_to_remove)

            return Response(
                EventDetailSerializer(event, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def tags(self, request, pk=None):
        """Получить список тегов мероприятия"""
        event = self.get_object()
        tags = event.tags.all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        # Проверяем и корректируем параметр ordering, если он некорректен
        ordering = request.query_params.get("ordering")
        if ordering and ordering not in [
            "start_at",
            "-start_at",
            "created_at",
            "-created_at",
            "average_rating",
            "-average_rating",
        ]:
            # Если значение некорректно, используем значение по умолчанию
            request.query_params._mutable = True
            request.query_params["ordering"] = "start_at"
            request.query_params._mutable = False

        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        summary="Список тегов",
        description="Получить список всех тегов. Поддерживается поиск и сортировка.",
        parameters=[
            OpenApiParameter(
                name="ordering",
                description="Поле для сортировки результатов (например, 'name' или '-name').",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="page",
                description="Номер страницы в пагинированном списке.",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="search",
                description="Поисковый запрос по названию или slug тега.",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: TagSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Пример ответа",
                value={
                    "count": 3,
                    "next": None,
                    "previous": None,
                    "results": [
                        {"id": 1, "name": "Python", "slug": "python"},
                        {"id": 2, "name": "Django", "slug": "django"},
                        {"id": 3, "name": "REST API", "slug": "rest-api"},
                    ],
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Создать тег",
        description="Создать новый тег. Доступно только администраторам.",
        request=TagSerializer,
        responses={
            201: TagSerializer,
            400: OpenApiExample(
                "Ошибка валидации",
                value={"name": ["Тег с таким названием уже существует."]},
                response_only=True,
            ),
            401: OpenApiExample(
                "Ошибка авторизации",
                value={"detail": "Учетные данные не были предоставлены."},
                response_only=True,
            ),
            403: OpenApiExample(
                "Доступ запрещен",
                value={
                    "detail": "У вас недостаточно прав для выполнения данного действия."
                },
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={"name": "Flask", "slug": "flask"},
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Получить тег",
        description="Получить подробную информацию о теге по его имени.",
        responses={
            200: TagSerializer,
            404: OpenApiExample(
                "Тег не найден",
                value={"detail": "Страница не найдена."},
                response_only=True,
            ),
        },
    ),
    partial_update=extend_schema(
        summary="Изменить тег (частично)",
        description="Изменить отдельные поля тега. Доступно только администраторам.",
        request=TagSerializer,
        responses={
            200: TagSerializer,
            400: OpenApiExample(
                "Ошибка валидации",
                value={"name": ["Тег с таким названием уже существует."]},
                response_only=True,
            ),
            401: OpenApiExample(
                "Ошибка авторизации",
                value={"detail": "Учетные данные не были предоставлены."},
                response_only=True,
            ),
            403: OpenApiExample(
                "Доступ запрещен",
                value={
                    "detail": "У вас недостаточно прав для выполнения данного действия."
                },
                response_only=True,
            ),
            404: OpenApiExample(
                "Тег не найден",
                value={"detail": "Страница не найдена."},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Пример запроса", value={"name": "Flask Framework"}, request_only=True
            )
        ],
    ),
    destroy=extend_schema(
        summary="Удалить тег",
        description="Удалить тег по его имени. Доступно только администраторам.",
        responses={
            204: None,
            401: OpenApiExample(
                "Ошибка авторизации",
                value={"detail": "Учетные данные не были предоставлены."},
                response_only=True,
            ),
            403: OpenApiExample(
                "Доступ запрещен",
                value={
                    "detail": "У вас недостаточно прав для выполнения данного действия."
                },
                response_only=True,
            ),
            404: OpenApiExample(
                "Тег не найден",
                value={"detail": "Страница не найдена."},
                response_only=True,
            ),
        },
    ),
)
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "id"]
    lookup_field = "name"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        return Tag.objects.all().order_by("name")
