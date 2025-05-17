from django.contrib.auth import get_user_model
from rest_framework import permissions, status, viewsets  # noqa: F401
from rest_framework.decorators import action
from rest_framework.response import Response

from users.serializers import UserCreateSerializer, UserSerializer, UserUpdateSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    API для работы с пользователями.

    list:
        Получить список всех пользователей (только для администраторов)
    retrieve:
        Получить детальную информацию о пользователе
    create:
        Зарегистрировать нового пользователя
    update:
        Обновить данные пользователя
    partial_update:
        Частично обновить данные пользователя
    destroy:
        Удалить пользователя (только для администраторов)
    me:
        Получить информацию о текущем пользователе
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
        # Обычные пользователи могут видеть только свой профиль
        if not self.request.user.is_staff:
            return User.objects.filter(id=self.request.user.id)
        return User.objects.all()

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Получить информацию о текущем пользователе"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
