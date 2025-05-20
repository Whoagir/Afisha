
# Система управления мероприятиями "Афиша"

Полноценная система для просмотра, бронирования и оценки мероприятий. Включает email-уведомления (тестовые через mailtrap) о подтверждении бронирования и других важных событиях.

## Возможности

- Просмотр мероприятий с фильтрацией и поиском
- Управление бронированиями
- Система оценок для мероприятий (только для прошедших и только участниками)
- Email-уведомления через gRPC-сервис
- Регистрация и аутентификация пользователей
- Очередь задач Celery для фоновой обработки
- Регулярная смена статуса мероприятий (через 2 часа после начала)
- Уведомления отправляются при бронировании, отмене и за час до начала события
- Ограничения: удаление события только в течение 1 часа после создания, изменение/удаление только организатором
- Фильтрация по локации, дате, статусу, наличию мест
- (Опционально) Теги, полнотекстовый поиск, сортировка по средней оценке организатора

## Архитектура

Проект построен на:
- Django и Django REST Framework (backend API)
- Celery (асинхронная обработка задач)
- gRPC (сервис email-уведомлений)
- PostgreSQL (база данных)
- Docker и Docker Compose (контейнеризация)

## Структура проекта

```
├── email_notification     # gRPC сервис email-уведомлений
├── src                    # Основное Django-приложение
│   ├── afisha             # Конфигурация проекта
│   ├── bookings           # Управление бронированиями
│   ├── common             # Общие утилиты и команды
│   ├── events             # Мероприятия и оценки
│   ├── notifications      # Система уведомлений
│   └── users              # Пользователи и профили
├── docker-compose.yaml    # Конфигурация Docker Compose
├── Dockerfile             # Dockerfile основного приложения
├── Dockerfile.email       # Dockerfile email-сервиса
└── pyproject.toml         # Зависимости Poetry
```

## Необходимое ПО

- Docker и Docker Compose
- Python 3.11
- Poetry (опционально, для локальной разработки)

## Быстрый старт

### Запуск через Docker

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/afisha.git
   cd afisha
   ```

2. Создайте файлы `.env` и `.env.db` в корне проекта:

   Пример `.env`:
   ```
    DATABASE_URL=postgres://afisha:afisha@db:5432/afisha
    CELERY_BROKER_URL=redis://redis:6379/0
    CELERY_RESULT_BACKEND=redis://redis:6379/0
    DJANGO_SECRET_KEY='your_secret_key'
    DEBUG=True
    ALLOWED_HOSTS=localhost,127.0.0.1
    GRPC_EMAIL_SERVER=email_notification:50051

    SMTP_HOST=sandbox.smtp.mailtrap.io
    SMTP_PORT=2525
    SMTP_USER=5f86640269fd8a
    SMTP_PASSWORD=87ca31b47c7f23
    DEFAULT_SENDER=noreply@example.com
    DJANGO_SUPERUSER_USERNAME=admin
    DJANGO_SUPERUSER_PASSWORD=12345
    DJANGO_SUPERUSER_EMAIL=admin@example.com


    GRPC_PORT=50051
    GRPC_HOST=email_notification

   ```

   Пример `.env.db`:
   ```
   POSTGRES_USER=afisha
    POSTGRES_PASSWORD=afisha
    POSTGRES_DB=afisha

   ```

3. Соберите и запустите контейнеры:
   ```bash
   docker-compose up -d --build
   ```

4. Проверьте применились ли миграции:

5. Суперпользователь зашит в .env, но проверить если ли по логам стоит:
6. Ну все, http://localhost:8000/api/docs/ ваш выбор (не забудьте что бы создать юзера надо выйти там из авторизации swager), по умолчанию admin 12345 можно получить токен



### Локальный запуск (разработка)

1. Установите зависимости через Poetry:
   ```bash
   poetry install
   ```

2. Настройте переменные окружения или создайте `.env`.

3. Примените миграции:
   ```bash
   poetry run python src/manage.py migrate
   ```

4. Запустите сервер разработки:
   ```bash
   poetry run python src/manage.py runserver
   ```

5. В отдельном терминале запустите Celery worker:
   ```bash
   poetry run celery -A afisha worker --loglevel=info
   ```

6. Запустите сервис email-уведомлений:
   ```bash
   cd email_notification
   pip install -r requirements.txt
   python server.py
   ```
7. Не забудьте про БДшку

## Основные API эндпоинты

Документация API доступна по адресу `/api/docs/` после запуска сервера.

## Линтинг и качество кода

Используются pre-commit хуки:

```bash
pre-commit install
pre-commit run --all-files
```


