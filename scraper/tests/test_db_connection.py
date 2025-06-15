#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к базе данных и проверки сохранения данных
"""

import asyncio
import sys
import os
import datetime

# Добавляем путь к модулю scraper
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.database.db_operations import connect_db, connect_db_async, save_data_to_postgresql_async, get_existing_ad_urls_async

async def test_database_connection():
    """Тестирование подключения к базе данных"""
    print("🧪 Testing database connection...")
    
    # Тест синхронного подключения
    print("1. Testing synchronous connection...")
    conn = connect_db()
    if conn:
        conn.close()
        print("✅ Synchronous connection successful!")
    else:
        print("❌ Synchronous connection failed!")
        return False
    
    # Тест асинхронного подключения
    print("2. Testing asynchronous connection...")
    conn_async = await connect_db_async()
    if conn_async:
        await conn_async.close()
        print("✅ Asynchronous connection successful!")
    else:
        print("❌ Asynchronous connection failed!")
        return False
    
    return True

async def test_data_operations():
    """Тестирование операций с данными"""
    print("\n🧪 Testing data operations...")
    
    # Тест получения существующих URL
    print("1. Testing get_existing_ad_urls_async...")
    try:
        existing_urls = await get_existing_ad_urls_async()
        print(f"✅ Successfully retrieved {len(existing_urls)} existing URLs")
    except Exception as e:
        print(f"❌ Error retrieving existing URLs: {e}")
        return False
    
    # Тест сохранения тестовых данных
    print("2. Testing save_data_to_postgresql_async...")
    test_data = [{
        "url": f"https://test.example.com/test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
        "title": "Test Car",
        "price_usd": 10000,
        "odometer": 50000,
        "username": "Test User",
        "phone_number": 1234567890,
        "image_url": "https://test.example.com/image.jpg",
        "images_count": 10,
        "car_number": "AA1234BB",
        "car_vin": "1HGBH41JXMN109186"
    }]
    
    try:
        await save_data_to_postgresql_async(test_data)
        print("✅ Successfully saved test data to database")
    except Exception as e:
        print(f"❌ Error saving test data: {e}")
        return False
    
    return True

async def main():
    """Основная функция тестирования"""
    print("🚀 Starting database connection and operations test...")
    
    # Тест подключения
    connection_ok = await test_database_connection()
    if not connection_ok:
        print("❌ Database connection test failed!")
        return
    
    # Тест операций с данными
    operations_ok = await test_data_operations()
    if not operations_ok:
        print("❌ Data operations test failed!")
        return
    
    print("\n✅ All database tests passed successfully!")
    print("🎉 Your database is ready for the async scraper!")

if __name__ == "__main__":
    asyncio.run(main()) 