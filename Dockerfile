# Stage 1 – build
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==1.7.1"

WORKDIR /app

# Копируем только файлы для установки зависимостей
COPY pyproject.toml poetry.lock* /app/

# Устанавливаем зависимости
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --without dev

# Копируем остальной код
COPY . /app/

# Stage 2 – runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

WORKDIR /app
COPY src/ /app/src/

ENV PYTHONPATH=/app/src

USER nobody

CMD ["gunicorn", "afisha.wsgi:application", "-b", "0.0.0.0:8000", "-w", "3"]
