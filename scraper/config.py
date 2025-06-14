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

    COMMON_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build=MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    } 