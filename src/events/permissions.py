# events/permissions.py
from rest_framework import permissions


class IsOrganizerOrReadOnly(permissions.BasePermission):
    """
    Разрешает редактирование только организатору события.
    """

    def has_object_permission(self, request, view, obj):
        # Разрешаем GET, HEAD, OPTIONS всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Разрешаем изменение только организатору
        return obj.organizer == request.user


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Разрешает редактирование только администраторам.
    """

    def has_permission(self, request, view):
        # Разрешаем GET, HEAD, OPTIONS всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Разрешаем изменение только администраторам
        return request.user and request.user.is_staff
