#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функции get_phone_from_ria
Тестирует извлечение номеров телефонов из объявлений AUTO.RIA
"""

import asyncio
import aiohttp
import sys
import os
from typing import List

# Добавляем путь к модулю scraper
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.scraper_core import get_phone_from_ria
from config import Config

# Тестовые URL объявлений AUTO.RIA (замените на актуальные)
TEST_URLS = [
    "https://auto.ria.com/uk/newauto/auto-renault-taliant-1999075.html",
    "https://auto.ria.com/uk/auto_audi_s5_38256694.html", 
    "https://auto.ria.com/uk/auto_audi_a4_38444076.html",
    "https://auto.ria.com/uk/auto_volkswagen_tiguan_38442747.html",
    "https://auto.ria.com/uk/auto_audi_a4_38444044.html"
]

async def test_single_phone_extraction(session: aiohttp.ClientSession, url: str) -> dict:
    """Тестирует извлечение телефона для одного объявления"""
    print(f"🔍 Тестируем URL: {url}")
    
    try:
        phones = await get_phone_from_ria(session, url)
        
        result = {
            "url": url,
            "success": True,
            "phones": phones,
            "phone_count": len(phones),
            "error": None
        }
        
        if phones:
            print(f"✅ Найдено телефонов: {len(phones)}")
            for i, phone in enumerate(phones, 1):
                print(f"   📞 Телефон {i}: {phone}")
        else:
            print("⚠️  Телефоны не найдены")
            
        return result
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {url}: {e}")
        return {
            "url": url,
            "success": False,
            "phones": [],
            "phone_count": 0,
            "error": str(e)
        }

async def test_phone_extraction_batch():
    """Тестирует извлечение телефонов для пакета объявлений"""
    print("🧪 Запуск тестирования извлечения телефонов...")
    print(f"📊 Количество тестовых URL: {len(TEST_URLS)}")
    print("-" * 60)
    
    # Настройка HTTP сессии
    timeout = aiohttp.ClientTimeout(
        total=Config.CONNECTION_TIMEOUT,
        connect=Config.CONNECT_TIMEOUT
    )
    
    connector = aiohttp.TCPConnector(
        limit=Config.CONNECTION_LIMIT,
        limit_per_host=Config.CONNECTION_LIMIT_PER_HOST,
        ttl_dns_cache=300,
        use_dns_cache=True,
    )
    
    results = []
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=Config.COMMON_HEADERS
    ) as session:
        
        # Тестируем каждый URL
        for i, url in enumerate(TEST_URLS, 1):
            print(f"\n📋 Тест {i}/{len(TEST_URLS)}")
            result = await test_single_phone_extraction(session, url)
            results.append(result)
            
            # Пауза между запросами
            if i < len(TEST_URLS):
                print(f"⏳ Пауза {Config.BATCH_DELAY} сек...")
                await asyncio.sleep(Config.BATCH_DELAY)
    
    return results

def print_test_summary(results: List[dict]):
    """Выводит сводку результатов тестирования"""
    print("\n" + "=" * 60)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    failed_tests = total_tests - successful_tests
    total_phones = sum(r["phone_count"] for r in results)
    
    print(f"🔢 Всего тестов: {total_tests}")
    print(f"✅ Успешных: {successful_tests}")
    print(f"❌ Неудачных: {failed_tests}")
    print(f"📞 Всего найдено телефонов: {total_phones}")
    print(f"📈 Процент успеха: {(successful_tests/total_tests)*100:.1f}%")
    
    if total_phones > 0:
        print(f"📊 Среднее количество телефонов на объявление: {total_phones/successful_tests:.1f}")
    
    print("\n📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        phone_info = f"({result['phone_count']} тел.)" if result["success"] else f"(Ошибка: {result['error']})"
        print(f"{status} Тест {i}: {phone_info}")
        
        if result["success"] and result["phones"]:
            for phone in result["phones"]:
                print(f"    📞 {phone}")
    
    print("\n" + "=" * 60)

async def test_with_custom_url():
    """Тестирует с пользовательским URL"""
    print("\n🔧 ТЕСТ С ПОЛЬЗОВАТЕЛЬСКИМ URL")
    print("-" * 40)
    
    # Здесь можно указать конкретный URL для тестирования
    custom_url = input("Введите URL объявления для тестирования (или Enter для пропуска): ").strip()
    
    if not custom_url:
        print("⏭️  Пропускаем тест с пользовательским URL")
        return
    
    timeout = aiohttp.ClientTimeout(
        total=Config.CONNECTION_TIMEOUT,
        connect=Config.CONNECT_TIMEOUT
    )
    
    connector = aiohttp.TCPConnector(
        limit=Config.CONNECTION_LIMIT,
        limit_per_host=Config.CONNECTION_LIMIT_PER_HOST,
    )
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=Config.COMMON_HEADERS
    ) as session:
        
        result = await test_single_phone_extraction(session, custom_url)
        print_test_summary([result])

async def main():
    """Главная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ ИЗВЛЕЧЕНИЯ ТЕЛЕФОНОВ ИЗ AUTO.RIA")
    print("=" * 60)
    
    try:
        # Основное тестирование
        results = await test_phone_extraction_batch()
        print_test_summary(results)
        
        # Дополнительный тест с пользовательским URL
        await test_with_custom_url()
        
        print("\n🎉 Тестирование завершено!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    print("📱 Запуск тестирования извлечения телефонов...")
    asyncio.run(main()) 