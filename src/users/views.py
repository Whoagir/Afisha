# src/users/views.py
from django.contrib.auth import get_user_model
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.serializers import UserCreateSerializer, UserSerializer, UserUpdateSerializer
from users.services.auth import register_user  # Добавляем импорт сервиса

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
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

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Получить информацию о текущем пользователе"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
