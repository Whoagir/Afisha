# Stage 1 – build
FROM python:3.11-slim AS builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --no-cache-dir "poetry==1.8.2"

# Копирование только файлов зависимостей для кэширования слоя
COPY pyproject.toml poetry.lock* /app/

# Экспорт зависимостей в requirements.txt для более быстрой установки
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2 – runtime
FROM python:3.11-slim

WORKDIR /app

# Установка только необходимых рантайм-зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование установленных пакетов из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копирование кода приложения
COPY src/ /app/

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER nobody
CMD ["gunicorn", "afisha.wsgi:application", "-b", "0.0.0.0:8000", "-w", "3"]
