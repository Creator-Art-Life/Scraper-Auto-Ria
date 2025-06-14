PHONY: up down logs rebuild clean-db

start:
	docker-compose up --build

down:
	docker-compose down

logs:
	docker-compose logs -f scraper

rebuild:
	docker-compose down
	docker-compose up --build -d

clean-db:
	./clear_db.bat 