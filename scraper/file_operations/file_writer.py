import json
import os
import datetime
import aiofiles
import asyncio

DUMP_DIR = "dumps"

def save_data_to_json(all_ads_data):
    if not os.path.exists(DUMP_DIR):
        os.makedirs(DUMP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DUMP_DIR, f"all_ads_data_{timestamp}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_ads_data, f, ensure_ascii=False, indent=4)
    print(f"All collected data saved to {filename}")


async def save_data_to_json_async(all_ads_data):
    """Асинхронная версия сохранения данных в JSON"""
    if not os.path.exists(DUMP_DIR):
        os.makedirs(DUMP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DUMP_DIR, f"all_ads_data_{timestamp}.json")
    
    # Подготавливаем JSON строку в отдельном потоке, чтобы не блокировать event loop
    json_data = await asyncio.get_event_loop().run_in_executor(
        None, 
        lambda: json.dumps(all_ads_data, ensure_ascii=False, indent=4)
    )
    
    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write(json_data)
    
    print(f"All collected data saved to {filename} (async)") 