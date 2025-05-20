# src/users/views.py
from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from events.serializers import EventListSerializer
from events.services.event import get_user_upcoming_events
from users.serializers import UserCreateSerializer, UserSerializer, UserUpdateSerializer
from users.services.auth import register_user

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        summary="Список пользователей",
        description="Получить список всех пользователей (права - для админа).",
        parameters=[
            OpenApiParameter(
                "ordering", str, OpenApiParameter.QUERY, description="Поле сортировки"
            ),
            OpenApiParameter(
                "page", int, OpenApiParameter.QUERY, description="Номер страницы"
            ),
            OpenApiParameter(
                "search", str, OpenApiParameter.QUERY, description="Поисковый запрос"
            ),
        ],
        responses={
            200: UserSerializer(many=True),
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
                            "username": "admin",
                            "email": "admin@example.com",
                            "first_name": "Admin",
                            "last_name": "User",
                        },
                        {
                            "id": 2,
                            "username": "user",
                            "email": "user@example.com",
                            "first_name": "User",
                            "last_name": "Test",
                        },
                    ],
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Создать пользователя",
        description="Регистрация нового пользователя.",
        request=UserCreateSerializer,
        responses={
            201: OpenApiExample(
                "Успешная регистрация",
                value={"refresh": "string", "access": "string"},
                response_only=True,
            ),
            400: OpenApiExample(
                "Ошибка валидации",
                value={"password_confirm": ["Пароли не совпадают"]},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "password123",
                    "password_confirm": "password123",
                    "first_name": "New",
                    "last_name": "User",
                },
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Получить пользователя",
        description="Получить информацию о пользователе по ID.",
        responses={200: UserSerializer},
    ),
    update=extend_schema(
        summary="Обновить пользователя",
        description="Полное обновление информации о пользователе.",
        request=UserUpdateSerializer,
        responses={200: UserSerializer},
    ),
    partial_update=extend_schema(
        summary="Частичное обновление пользователя",
        description="Частичное обновление информации о пользователе.",
        request=UserUpdateSerializer,
        responses={200: UserSerializer},
    ),
    destroy=extend_schema(
        summary="Удалить пользователя",
        description="Удалить пользователя по ID.",
        responses={204: None},
    ),
    me=extend_schema(
        summary="Текущий пользователь",
        description="Получить или изменить информацию о текущем пользователе.",
        methods=["GET", "PUT", "PATCH", "DELETE"],
        request=UserUpdateSerializer,
        responses={
            200: UserSerializer,
            204: None,
            400: OpenApiExample(
                "Ошибка", value={"error": "string"}, response_only=True
            ),
            401: OpenApiExample(
                "Неавторизован", value={"detail": "string"}, response_only=True
            ),
        },
    ),
)
class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    API для работы с пользователями.
    """

    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        elif self.action in ["list", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return User.objects.filter(id=self.request.user.id)
        return User.objects.all().prefetch_related("groups", "user_permissions")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Используем сервис для создания пользователя
        tokens = register_user(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data.get("first_name", ""),
            last_name=serializer.validated_data.get("last_name", ""),
        )

        # Возвращаем токены в ответе
        return Response(tokens, status=201)

    @action(detail=False, methods=["get", "patch", "delete"])
    def me(self, request):
        """
        Получить или изменить информацию о текущем пользователе.

        GET: Получить информацию о текущем пользователе
        PUT: Полное обновление данных текущего пользователя
        PATCH: Частичное обновление данных текущего пользователя
        DELETE: Удаление аккаунта текущего пользователя
        """
        user = request.user

        if request.method == "GET":
            serializer = UserSerializer(user)
            return Response(serializer.data)

        elif request.method in ["PUT", "PATCH"]:
            partial = request.method == "PATCH"
            serializer = UserUpdateSerializer(user, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        elif request.method == "DELETE":
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Предстоящие мероприятия пользователя",
        description="Получить список предстоящих мероприятий для текущего пользователя или пользователя по ID.",
        responses={
            200: EventListSerializer(many=True),
            404: {"description": "Пользователь не найден"},
        },
    )
    @action(detail=True, methods=["get"])
    def upcoming_events(self, request, pk=None):
        """
        Получить список предстоящих мероприятий пользователя.

        Если запрашиваются мероприятия для другого пользователя,
        необходимы права администратора.
        """
        # Получаем пользователя
        if pk == "me" or int(pk) == request.user.id:
            user = request.user
        else:
            # Если запрашиваются мероприятия другого пользователя, проверяем права
            if not request.user.is_staff:
                return Response(
                    {
                        "detail": "У вас нет прав для просмотра мероприятий других пользователей."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            try:
                user = User.objects.get(pk=pk)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Пользователь не найден."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Получаем предстоящие мероприятия
        events = (
            get_user_upcoming_events(user)
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


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Сохраняем refresh токен в куки
            response.set_cookie(
                "refresh_token",
                response.data["refresh"],
                httponly=True,
                max_age=86400,  # 1 день
                samesite="Strict",
            )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # Если refresh токен не указан в теле запроса, но есть в куки
        if "refresh" not in request.data and "refresh_token" in request.COOKIES:
            request.data["refresh"] = request.COOKIES.get("refresh_token")

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and "refresh" in response.data:
            # Обновляем refresh токен в куки
            response.set_cookie(
                "refresh_token",
                response.data["refresh"],
                httponly=True,
                max_age=86400,  # 1 день
                samesite="Strict",
            )
        return response
