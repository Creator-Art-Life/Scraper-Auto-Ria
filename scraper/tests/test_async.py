#!/usr/bin/env python3
"""
Тестовый скрипт для проверки асинхронной версии скрапера
"""

import asyncio
import sys
import os

# Добавляем путь к модулю scraper
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.main import perform_scraping_job_async

async def test_async_scraper():
    """Тестирование асинхронного скрапера"""
    print("🧪 Starting async scraper test...")
    
    try:
        await perform_scraping_job_async()
        print("✅ Async scraper test completed successfully!")
    except Exception as e:
        print(f"❌ Async scraper test failed: {e}")
        raise

if __name__ == "__main__":
    print("🚀 Running async scraper test...")
    asyncio.run(test_async_scraper()) 