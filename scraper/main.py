import time
import aiohttp
import asyncio
import threading
import copy
import datetime
import sys
import signal
import os
import argparse
from apscheduler.schedulers.background import BackgroundScheduler

from scraper.core.scraper_core import collect_ad_urls_from_page, parse_ad_page, fetch_html_with_aiohttp, process_ad_batch
from scraper.database.db_operations import save_data_to_postgresql, get_existing_ad_urls, connect_db, save_data_to_postgresql_async, get_existing_ad_urls_async
from scraper.file_operations.file_writer import save_data_to_json
from scraper.config import Config

# Global list to store all collected advertisement data
all_ads_data = []
# Lock for thread-safe access to all_ads_data
all_ads_data_lock = threading.Lock()
# Event to signal the main thread to stop
stop_main_thread_event = threading.Event()
# Event to signal auto-save thread to stop
auto_save_stop_event = threading.Event()
# Track the index of the last saved record to avoid re-saving
last_saved_index = 0
last_saved_index_lock = threading.Lock()

def check_database_connection():
    """Проверка подключения к базе данных при старте"""
    print("🔍 Checking database connection...")
    conn = connect_db()
    if conn:
        conn.close()
        print("✅ Database connection successful!")
        return True
    else:
        print("❌ Database connection failed!")
        return False

def auto_save_worker():
    """Worker function for automatic saving of collected data"""
    global last_saved_index
    
    if not Config.AUTO_SCRAPE_TIME:
        return
    
    try:
        save_interval = int(Config.AUTO_SCRAPE_TIME)
        print(f"🔄 Auto-save worker started with {save_interval} second interval")
        
        while not auto_save_stop_event.is_set():
            # Wait for the specified interval or until stop event is set
            if auto_save_stop_event.wait(timeout=save_interval):
                break  # Stop event was set
            
            # Save only new data
            with all_ads_data_lock, last_saved_index_lock:
                total_records = len(all_ads_data)
                if total_records > last_saved_index:
                    # Get only new records that haven't been saved yet
                    new_records = all_ads_data[last_saved_index:]
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n💾 [{current_time}] Auto-saving {len(new_records)} new ads to PostgreSQL (total: {total_records})...")
                    try:
                        # Используем асинхронную функцию в отдельном event loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(save_data_to_postgresql_async(new_records.copy()))
                        loop.close()
                        last_saved_index = total_records  # Update the index of last saved record
                        print(f"✅ [{current_time}] Auto-save completed successfully. Saved records {last_saved_index - len(new_records) + 1}-{last_saved_index}")
                    except Exception as e:
                        print(f"❌ [{current_time}] Auto-save failed: {e}")
                else:
                    print(f"📭 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No new data to auto-save (total: {total_records})")
                    
    except ValueError:
        print(f"⚠️ Warning: Invalid AUTO_SCRAPE_TIME format '{Config.AUTO_SCRAPE_TIME}'. Should be number of seconds.")
    except Exception as e:
        print(f"❌ Auto-save worker error: {e}")
    finally:
        print("🔄 Auto-save worker stopped")

async def save_batch_to_db(batch_results):
    """Асинхронное сохранение пакета данных в базу"""
    if batch_results:
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"💾 [{current_time}] Saving {len(batch_results)} ads to database...")
            await save_data_to_postgresql_async(batch_results)
            print(f"✅ [{current_time}] Successfully saved {len(batch_results)} ads to database")
            return True
        except Exception as e:
            print(f"❌ Error saving batch to database: {e}")
            return False
    return False

async def perform_scraping_job_async():
    """Асинхронная функция скрапинга"""
    global all_ads_data, last_saved_index
    with all_ads_data_lock, last_saved_index_lock:
        all_ads_data.clear() # Clear data from previous runs to avoid accumulating old data on new runs
        last_saved_index = 0  # Reset the saved index for new scraping job

    if not Config.AUTO_RIA_START_URL:
        print("AUTO_RIA_START_URL is not set in the .env file. Please set it to a valid URL, e.g., https://auto.ria.com/uk/car/used/")
        return

    print(f"\n--- [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting daily scraping job (ASYNC) ---")
    print(f"🔧 Configuration:")
    print(f"   - Database Host: {Config.PG_HOST}")
    print(f"   - Database Name: {Config.PG_DBNAME}")
    print(f"   - Scrape Time: {Config.SCRAPE_TIME}")
    print(f"   - Dump Time: {Config.DUMP_TIME}")
    print(f"   - Auto-save Interval: {Config.AUTO_SCRAPE_TIME} seconds" if Config.AUTO_SCRAPE_TIME else "   - Auto-save: Disabled")
    print(f"   - Start URL: {Config.AUTO_RIA_START_URL}")
    print(f"   - Mode: ASYNCHRONOUS (High Performance)")
    print(f"")
    print(f"⚙️ Performance Parameters:")
    print(f"   - Semaphore Limit: {Config.SEMAPHORE_LIMIT} concurrent requests")
    print(f"   - Batch Size: {Config.BATCH_SIZE} ads per batch")
    print(f"   - Batch Delay: {Config.BATCH_DELAY}s between batches")
    print(f"   - Page Delay: {Config.PAGE_DELAY}s between pages")
    print(f"   - Connection Limit: {Config.CONNECTION_LIMIT} total, {Config.CONNECTION_LIMIT_PER_HOST} per host")
    print(f"   - Timeouts: {Config.CONNECTION_TIMEOUT}s total, {Config.CONNECT_TIMEOUT}s connect")
    
    start_time = time.time()

    # Start auto-save worker if AUTO_SCRAPE_TIME is configured
    auto_save_thread = None
    if Config.AUTO_SCRAPE_TIME:
        auto_save_stop_event.clear()
        auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
        auto_save_thread.start()

    print("Fetching existing ad URLs from the database (async)...")
    existing_ad_urls = await get_existing_ad_urls_async()
    print(f"Found {len(existing_ad_urls)} URLs already in the database.")

    # Создаем семафор для ограничения количества одновременных запросов
    semaphore = asyncio.Semaphore(Config.SEMAPHORE_LIMIT)
    
    # Настройка aiohttp session с настраиваемыми параметрами
    cookie_jar = aiohttp.CookieJar()
    connector = aiohttp.TCPConnector(
        limit=Config.CONNECTION_LIMIT, 
        limit_per_host=Config.CONNECTION_LIMIT_PER_HOST
    )
    timeout = aiohttp.ClientTimeout(
        total=Config.CONNECTION_TIMEOUT, 
        connect=Config.CONNECT_TIMEOUT
    )
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        cookie_jar=cookie_jar,
        headers=Config.COMMON_HEADERS
    ) as session:
        
        # Устанавливаем cookies
        session.cookie_jar.update_cookies({
            'chk': '1',
            '__utmc': '79960839',
            '__utmz': '79960839.1749807882.1.1.utmcsr=google|utmccn=(organic)|utmcmd=organic|utmctr=(not%20provided)',
            'showNewFeatures': '7',
            'extendedSearch': '1',
            'informerIndex': '1',
            '_gcl_au': '1.1.696652926.1749807882',
            '_504c2': 'http://10.42.12.49:3000',
            '_ga': 'GA1.1.76946374.1749807883',
            '_fbp': 'fb.1.1749807883050.284932067592788166',
            'gdpr': '[2,3]',
            'ui': 'd166f29f660ec9a4',
            'showNewNextAdvertisement': '-10',
            'PHPSESSID': 'yUVRySHhF47tGqsLEO9GHZLcJq2osvFu'
        })

        current_page_url = Config.AUTO_RIA_START_URL
        page_count = 0
        total_saved = 0
        
        while True:
            page_count += 1
            print(f"\n🔍 Page {page_count}: Collecting ad URLs from: {current_page_url}")
            
            try:
                ad_urls, next_page_url = await collect_ad_urls_from_page(session, current_page_url)
            except Exception as e:
                print(f"❌ Error collecting URLs from page {page_count}: {e}")
                break

            if ad_urls:
                print(f"📋 Found {len(ad_urls)} advertisements on page {page_count}. Processing in parallel...")
                
                # Обрабатываем объявления пакетами с настраиваемым размером
                batch_size = Config.BATCH_SIZE
                for i in range(0, len(ad_urls), batch_size):
                    batch_urls = ad_urls[i:i + batch_size]
                    print(f"🔄 Processing batch {i//batch_size + 1}/{(len(ad_urls) + batch_size - 1)//batch_size} ({len(batch_urls)} ads)...")
                    
                    try:
                        batch_results = await process_ad_batch(session, batch_urls, existing_ad_urls, semaphore)
                        
                        if batch_results:
                            # Добавляем в глобальный список
                            with all_ads_data_lock:
                                all_ads_data.extend(batch_results)
                            
                            # Сразу сохраняем в базу данных
                            saved_successfully = await save_batch_to_db(batch_results)
                            if saved_successfully:
                                total_saved += len(batch_results)
                                with last_saved_index_lock:
                                    last_saved_index = len(all_ads_data)
                            
                            print(f"✅ Successfully processed and saved {len(batch_results)} ads from batch (Total saved: {total_saved})")
                        else:
                            print("📭 No new ads found in this batch")
                        
                        # Настраиваемая пауза между пакетами
                        if Config.BATCH_DELAY > 0:
                            print(f"⏳ Waiting {Config.BATCH_DELAY}s before next batch...")
                            await asyncio.sleep(Config.BATCH_DELAY)
                        
                    except Exception as e:
                        print(f"❌ Error processing batch: {e}")
                        continue
                        
            else:
                print("📭 No advertisement links found on this page. Stopping scraping.")
                break

            if next_page_url:
                current_page_url = next_page_url
                print(f"➡️ Navigating to next page: {current_page_url}")
                if Config.PAGE_DELAY > 0:
                    print(f"⏳ Waiting {Config.PAGE_DELAY}s before next page...")
                    await asyncio.sleep(Config.PAGE_DELAY)
            else:
                print("🏁 No next page found. Stopping scraping.")
                break

    # Stop auto-save worker
    if auto_save_thread:
        auto_save_stop_event.set()
        auto_save_thread.join(timeout=5)  # Wait up to 5 seconds for thread to finish

    end_time = time.time()
    total_elapsed_time = end_time - start_time
    print(f"--- ⏱️ Finished scraping job. Total elapsed time: {total_elapsed_time:.2f} seconds ---")
    print(f"--- 📊 Processed {page_count} pages, collected {len(all_ads_data)} ads, saved {total_saved} ads ---")

    # Save any remaining unsaved data
    with all_ads_data_lock, last_saved_index_lock:
        total_records = len(all_ads_data)
        if total_records > last_saved_index:
            remaining_records = all_ads_data[last_saved_index:]
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- 💾 [{current_time}] Saving {len(remaining_records)} remaining ads to PostgreSQL (async) ---")
            await save_data_to_postgresql_async(remaining_records)
            last_saved_index = total_records
            print(f"--- ✅ [{current_time}] Finished saving remaining ads ---")
        elif total_records > 0:
            print(f"\n--- 📭 All {total_records} ads have already been saved during processing ---")
        else:
            print(f"\n--- 📭 No ads were collected during this scraping session ---")

def perform_scraping_job():
    """Синхронная обертка для асинхронной функции скрапинга"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(perform_scraping_job_async())
    finally:
        loop.close()

def perform_dump_job():
    with all_ads_data_lock:
        data_to_dump = copy.deepcopy(all_ads_data)
    
    if data_to_dump:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- [{current_time}] Initiating daily data dump to JSON ---")
        save_data_to_json(data_to_dump)
        print(f"--- [{current_time}] Finished daily data dump ---")
    else:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- [{current_time}] No data to dump to JSON ---")


def graceful_exit(scheduler):
    print("\n--- Shutting down scheduler and exiting application ---")
    scheduler.shutdown()
    stop_main_thread_event.set()

def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) and SIGTERM signals"""
    print(f"\n🛑 Received signal {signum}. Shutting down...")
    
    # Stop auto-save worker if running
    auto_save_stop_event.set()
    
    # Save any unsaved collected data to database before shutdown
    with all_ads_data_lock, last_saved_index_lock:
        total_records = len(all_ads_data)
        if total_records > last_saved_index:
            remaining_records = all_ads_data[last_saved_index:]
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n💾 [{current_time}] Saving {len(remaining_records)} unsaved ads to PostgreSQL before shutdown...")
            try:
                # Используем асинхронную функцию в отдельном event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(save_data_to_postgresql_async(remaining_records))
                loop.close()
                print(f"✅ [{current_time}] Successfully saved {len(remaining_records)} unsaved records before shutdown")
            except Exception as e:
                print(f"❌ [{current_time}] Error saving data to database: {e}")
        elif total_records > 0:
            print(f"📭 All {total_records} collected ads have already been saved")
        else:
            print("📭 No data to save to database")
    
    stop_main_thread_event.set()
    # Force exit after a timeout (increased to allow time for database save)
    threading.Timer(10.0, lambda: os._exit(1)).start()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AutoRia Scraper (Async Version)')
    parser.add_argument('--run-now', action='store_true', 
                       help='Run scraping immediately without using scheduler')
    parser.add_argument('--dump-now', action='store_true',
                       help='Run data dump immediately after scraping')
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 Starting AutoRia Scraper (ASYNC VERSION)...")
    print(f"📅 Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Проверка подключения к базе данных при старте
    if not check_database_connection():
        print("❌ Cannot start without database connection. Exiting...")
        sys.exit(1)
    
    print(f"🔧 Configuration:")
    print(f"   - Database Host: {Config.PG_HOST}")
    print(f"   - Database Name: {Config.PG_DBNAME}")
    print(f"   - Scrape Time: {Config.SCRAPE_TIME}")
    print(f"   - Dump Time: {Config.DUMP_TIME}")
    print(f"   - Auto-save Interval: {Config.AUTO_SCRAPE_TIME} seconds" if Config.AUTO_SCRAPE_TIME else "   - Auto-save: Disabled")
    print(f"   - Start URL: {Config.AUTO_RIA_START_URL}")
    print(f"   - Mode: ASYNCHRONOUS (High Performance)")
    print(f"")
    print(f"⚙️ Performance Parameters:")
    print(f"   - Semaphore Limit: {Config.SEMAPHORE_LIMIT} concurrent requests")
    print(f"   - Batch Size: {Config.BATCH_SIZE} ads per batch")
    print(f"   - Batch Delay: {Config.BATCH_DELAY}s between batches")
    print(f"   - Page Delay: {Config.PAGE_DELAY}s between pages")
    print(f"   - Connection Limit: {Config.CONNECTION_LIMIT} total, {Config.CONNECTION_LIMIT_PER_HOST} per host")
    print(f"   - Timeouts: {Config.CONNECTION_TIMEOUT}s total, {Config.CONNECT_TIMEOUT}s connect")
    
    # Check if immediate execution is requested
    if args.run_now:
        print("🏃‍♂️ Running scraper immediately (--run-now flag detected)")
        try:
            # Run scraping job immediately
            perform_scraping_job()
            
            # Run dump job if requested
            if args.dump_now:
                print("💾 Running data dump immediately (--dump-now flag detected)")
                perform_dump_job()
            
            print("✅ Immediate execution completed. Exiting.")
            sys.exit(0)
            
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 Immediate execution interrupted. Shutting down...")
            # Stop auto-save worker if running
            auto_save_stop_event.set()
            # Save any unsaved collected data before exit
            with all_ads_data_lock, last_saved_index_lock:
                total_records = len(all_ads_data)
                if total_records > last_saved_index:
                    remaining_records = all_ads_data[last_saved_index:]
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n💾 [{current_time}] Saving {len(remaining_records)} unsaved ads to PostgreSQL before shutdown...")
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(save_data_to_postgresql_async(remaining_records))
                        loop.close()
                        print(f"✅ [{current_time}] Successfully saved {len(remaining_records)} unsaved records before shutdown")
                    except Exception as e:
                        print(f"❌ [{current_time}] Error saving data to database: {e}")
                elif total_records > 0:
                    print(f"📭 All {total_records} collected ads have already been saved")
                else:
                    print("📭 No data to save to database")
            print("🏁 Immediate execution terminated.")
            sys.exit(0)
    
    # Continue with scheduler-based execution if --run-now not specified
    scheduler = BackgroundScheduler()

    if Config.SCRAPE_TIME:
        try:
            scrape_hour, scrape_minute = map(int, Config.SCRAPE_TIME.split(':'))
            scheduler.add_job(perform_scraping_job, 'cron', hour=scrape_hour, minute=scrape_minute)
            print(f"⏰ Scheduled scraping job to run daily at {Config.SCRAPE_TIME}")
        except ValueError:
            print(f"⚠️ Warning: Invalid SCRAPE_TIME format '{Config.SCRAPE_TIME}'. Please use HH:MM.")
    else:
        print("⚠️ Warning: SCRAPE_TIME is not set in .env. Scraping will not be scheduled.")

    if Config.DUMP_TIME:
        try:
            dump_hour, dump_minute = map(int, Config.DUMP_TIME.split(':'))
            scheduler.add_job(perform_dump_job, 'cron', hour=dump_hour, minute=dump_minute)
            print(f"⏰ Scheduled data dump job to run daily at {Config.DUMP_TIME}")
        except ValueError:
            print(f"⚠️ Warning: Invalid DUMP_TIME format '{Config.DUMP_TIME}'. Please use HH:MM.")
    else:
        print("⚠️ Warning: DUMP_TIME is not set in .env. Data dumping will not be scheduled.")
    
    if Config.DUMP_TIME:
        try:
            dump_hour, dump_minute = map(int, Config.DUMP_TIME.split(':'))
            # Schedule graceful_exit slightly after DUMP_TIME
            exit_minute = (dump_minute + 5) % 60
            exit_hour = dump_hour + (dump_minute + 5) // 60
            if exit_hour > 23:
                exit_hour = exit_hour % 24
            
            scheduler.add_job(graceful_exit, 'cron', args=[scheduler], hour=exit_hour, minute=exit_minute)
            print(f"⏰ Scheduled graceful exit at {exit_hour:02d}:{exit_minute:02d}")
        except ValueError:
            print(f"⚠️ Warning: Could not schedule graceful exit due to invalid DUMP_TIME format '{Config.DUMP_TIME}'.")

    scheduler.start()
    print("✅ Scheduler started. Waiting for scheduled tasks...")
    print("📊 Use 'docker-compose logs -f scraper' to monitor the application")
    print("🛑 Press Ctrl+C to stop the application")

    try:
        while not stop_main_thread_event.is_set():
            time.sleep(0.1)  # Shorter sleep for more responsive shutdown
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Application interrupted. Shutting down scheduler...")
        stop_main_thread_event.set()
    finally:
        try:
            print("🔄 Shutting down scheduler...")
            scheduler.shutdown(wait=False)  # Don't wait for jobs to complete
            print("✅ Scheduler shut down. Exiting.")
        except Exception as e:
            print(f"⚠️ Error during shutdown: {e}")
        finally:
            print("🏁 Application terminated.")
            os._exit(0)  # Force exit
