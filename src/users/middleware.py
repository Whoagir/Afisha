# src/users/middleware.py
from datetime import datetime, timedelta

import jwt
from rest_framework_simplejwt.tokens import RefreshToken


class TokenRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Проверяем наличие токена в заголовке (ну это и прикол, можно попасть в 4-е измерение токенов)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # Декодируем токен без проверки
                payload = jwt.decode(token, options={"verify_signature": False})

                # Проверяем, истекает ли токен в ближайшее время (например, через 30 минут)
                exp = datetime.fromtimestamp(payload["exp"])
                now = datetime.now()

                # Если токен истекает в течение 30 минут, обновляем его
                if exp - now < timedelta(minutes=30):
                    # Получаем refresh токен из куки или сессии
                    refresh_token = request.COOKIES.get("refresh_token")
                    if refresh_token:
                        try:
                            refresh = RefreshToken(refresh_token)
                            # Создаем новый access токен
                            new_access_token = str(refresh.access_token)
                            # Устанавливаем новый токен в заголовок
                            request.META["HTTP_AUTHORIZATION"] = (
                                f"Bearer {new_access_token}"
                            )
                        except Exception:
                            # Если не удалось обновить токен, продолжаем с текущим
                            pass
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                # Если токен недействителен, просто продолжаем
                pass

        response = self.get_response(request)
        return response
