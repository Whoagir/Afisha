# src/users/services/auth.py
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def register_user(username, email, password, first_name="", last_name=""):
    """
    Регистрирует нового пользователя и возвращает токены.

    Args:
        username (str): Имя пользователя.
        email (str): Email пользователя.
        password (str): Пароль.
        first_name (str, optional): Имя. По умолчанию пустая строка.
        last_name (str, optional): Фамилия. По умолчанию пустая строка.

    Returns:
        dict: Словарь с refresh и access токенами.

    Raises:
        django.contrib.auth.models.User.DoesNotExist: Если пользователь уже существует.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
