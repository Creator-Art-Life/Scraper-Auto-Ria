FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY scraper/requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY scraper/ ./scraper/
COPY dumps/ ./dumps/

# Создание директории для дампов если её нет
RUN mkdir -p dumps

# Установка переменных окружения для Python
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Создание пользователя для безопасности
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

# Команда по умолчанию
CMD ["bash", "-c", "python -m scraper.main & wait $!; tail -f /dev/null"]