import asyncio
import aiohttp
from scraper.core.scraper_core import parse_ad_page, fetch_html_with_aiohttp
from scraper.config import Config

async def test_newauto_parsing():
    """Тестирование парсинга страницы нового автомобиля"""
    
    # URL для тестирования
    test_url = "https://auto.ria.com/uk/newauto/auto-peugeot-2008-2000775.html"
    
    print(f"🧪 Тестирование парсинга newauto: {test_url}")
    print("=" * 80)
    
    # Создаем HTTP сессию
    timeout = aiohttp.ClientTimeout(
        total=Config.CONNECTION_TIMEOUT,
        connect=Config.CONNECT_TIMEOUT
    )
    
    connector = aiohttp.TCPConnector(
        limit=Config.CONNECTION_LIMIT,
        limit_per_host=Config.CONNECTION_LIMIT_PER_HOST
    )
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector
    ) as session:
        try:
            # Получаем HTML страницы
            print("📥 Загружаем HTML страницы...")
            html_content = await fetch_html_with_aiohttp(session, test_url)
            
            if not html_content:
                print("❌ Не удалось загрузить HTML страницы")
                return
            
            print(f"✅ HTML загружен, размер: {len(html_content)} символов")
            
            # Парсим страницу
            print("🔍 Парсим данные объявления...")
            ad_data = await parse_ad_page(test_url, html_content, session)
            
            if ad_data:
                print("✅ Данные успешно извлечены:")
                print("-" * 40)
                for key, value in ad_data.items():
                    print(f"{key.replace('_', ' ').title()}: {value}")
                print("-" * 40)
                
                # Проверяем ключевые поля
                checks = [
                    ("Title", ad_data.get("title")),
                    ("Price USD", ad_data.get("price_usd")),
                    ("Username", ad_data.get("username")),
                    ("Image URL", ad_data.get("image_url")),
                    ("Images Count", ad_data.get("images_count"))
                ]
                
                print("\n📊 Проверка ключевых полей:")
                for field_name, field_value in checks:
                    status = "✅" if field_value is not None else "❌"
                    print(f"{status} {field_name}: {'OK' if field_value else 'Missing'}")
                
            else:
                print("❌ Не удалось извлечь данные из объявления")
                
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_newauto_parsing()) 