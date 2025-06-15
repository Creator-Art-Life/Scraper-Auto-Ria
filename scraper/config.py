from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    AUTO_RIA_START_URL = os.getenv("AUTO_RIA_START_URL")
    
    PG_HOST = os.getenv("PG_HOST")
    PG_DBNAME = os.getenv("PG_DBNAME")
    PG_USER = os.getenv("PG_USER")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    PG_PORT = int(os.getenv("PG_PORT", 5432)) # Convert to int, default 5432

    SCRAPE_TIME = os.getenv("SCRAPE_TIME") # e.g., "01:00"
    DUMP_TIME = os.getenv("DUMP_TIME")     # e.g., "03:00"
    AUTO_SCRAPE_TIME = os.getenv("AUTO_SCRAPE_TIME") # e.g., "30" for 30 seconds, "60" for 1 minute

    # Новые параметры производительности
    SEMAPHORE_LIMIT = int(os.getenv("SEMAPHORE_LIMIT", 2))  # Максимум одновременных запросов
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 5))  # Размер пакета объявлений
    BATCH_DELAY = float(os.getenv("BATCH_DELAY", 2.0))  # Пауза между пакетами в секундах
    PAGE_DELAY = float(os.getenv("PAGE_DELAY", 3.0))  # Пауза между страницами в секундах
    
    # Параметры HTTP соединений
    CONNECTION_LIMIT = int(os.getenv("CONNECTION_LIMIT", 50))  # Общий лимит соединений
    CONNECTION_LIMIT_PER_HOST = int(os.getenv("CONNECTION_LIMIT_PER_HOST", 20))  # Лимит на хост
    CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", 30))  # Общий таймаут
    CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", 10))  # Таймаут подключения

    COMMON_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build=MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    } 