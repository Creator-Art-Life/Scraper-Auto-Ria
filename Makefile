.PHONY: start stop logs rebuild clean status test-db

# Запуск сервиса
start:
	docker-compose up -d

# Остановка сервиса
stop:
	docker-compose down

# Просмотр логов
logs:
	docker-compose logs -f scraper

# Пересборка и перезапуск
rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# Статус сервиса
status:
	docker-compose ps

# Очистка
clean:
	docker-compose down
	docker system prune -f

# Тест подключения к базе данных
test-db:
	docker-compose exec scraper python -c "from scraper.database.db_operations import connect_db; conn = connect_db(); print('✅ Database connection successful!' if conn else '❌ Database connection failed!'); conn and conn.close()"

# Запуск скрапинга вручную (для тестирования)
run-scraper:
	docker-compose exec scraper python -c "from scraper.main import perform_scraping_job; perform_scraping_job()"

# Создание дампа вручную
run-dump:
	docker-compose exec scraper python -c "from scraper.main import perform_dump_job; perform_dump_job()"

# Просмотр переменных окружения
show-env:
	docker-compose exec scraper env | grep -E "(PG_|AUTO_RIA|SCRAPE_|DUMP_)" 