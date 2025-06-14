import time
import requests
import threading
import copy
import datetime

from scraper.core.scraper_core import collect_ad_urls_from_page, parse_ad_page, fetch_html_with_requests
from scraper.database.db_operations import save_data_to_postgresql, get_existing_ad_urls
from scraper.file_operations.file_writer import save_data_to_json
from scraper.config import Config

# Global list to store all collected advertisement data
all_ads_data = []
# Lock for thread-safe access to all_ads_data
all_ads_data_lock = threading.Lock()
# Event to signal the saving thread to stop
stop_saving_event = threading.Event()

def periodic_save_task(save_interval_minutes=1):
    while not stop_saving_event.is_set():
        time.sleep(save_interval_minutes * 60) # Wait for the interval
        if stop_saving_event.is_set():
            break

        with all_ads_data_lock:
            # Make a copy of the data to avoid issues while the main thread modifies it
            data_to_save = copy.deepcopy(all_ads_data)
            # Clear the list after copying, so we only save new data next time
            all_ads_data.clear()
        
        if data_to_save:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- [{current_time}] Initiating periodic save of {len(data_to_save)} new ads to PostgreSQL ---")
            save_data_to_postgresql(data_to_save)
            print(f"--- [{current_time}] Finished periodic save ---")


if __name__ == "__main__":
    if not Config.AUTO_RIA_START_URL:
        print("AUTO_RIA_START_URL is not set in the .env file. Please set it to a valid URL, e.g., https://auto.ria.com/uk/car/used/")
    else:
        # all_ads_data is now a global variable
        start_time = time.time() # Record start time
        
        print("Fetching existing ad URLs from the database...")
        existing_ad_urls = get_existing_ad_urls()
        print(f"Found {len(existing_ad_urls)} URLs already in the database.")
        
        # Initialize a requests Session
        session = requests.Session()
        # Add the static Cookie header to the session directly once
        session.headers.update(Config.COMMON_HEADERS)
        session.headers.update({'Cookie': 'chk=1; __utmc=79960839; __utmz=79960839.1749807882.1.1.utmcsr=google|utmccn=(organic)|utmcmd=organic|utmctr=(not%20provided); showNewFeatures=7; extendedSearch=1; informerIndex=1; _gcl_au=1.1.696652926.1749807882; _504c2=http://10.42.12.49:3000; _ga=GA1.1.76946374.1749807883; _fbp=fb.1.1749807883050.284932067592788166; gdpr=[2,3]; ui=d166f29f660ec9a4; showNewNextAdvertisement=-10; PHPSESSID=eyJ3ZWJTZXNzaW9uQXZhaWxhYmxlIjp0cnVlLCJ3ZWJQZXJzb25JZCI6MCwid2ViQ2xpZW50SWQiOjM1MTMxODQ5MjcsIndlYkNsaWVudENvZGUiOjE3MTIyNDUxNTYsIndlYkNsaWVudENvb2tpZSI6ImQxNjZmMjlmNjYwZWM5YTQiLCJfZXhwaXJlIjoxNzQ5ODk0NDU3NTA4LCJfbWF4QWdlIjo4NjQwMDAwMH0=; _gcl_au=1.1.696652926.1749807882; __utma=79960839.52955078.1749807882.1749807882.1749888108.2; ria_sid=85621522490013; test_new_features=471; advanced_search_test=42; PHPSESSID=yUVRySHhF47tGqsLEO9GHZLcJq2osvFu; __gads=ID=357ddd82150197a9:T=1749808075:RT=1749890584:S=ALNI_MaYlNw99vGLw5YT57y-0ottkquT8Q; __gpi=UID=0000111e88d3917e:T=1749808075:RT=1749890584:S=AA-AfjapKWw5csLyi8WbFzcgx7_9; _ga=GA1.1.76946374.1749807883; _clck=124xdts%7C2%7Cfwr%7C0%7C1991; PSP_ID=d6374a6a63b8471567eadc00172e0f0346120a00cde02eb39884db30b0e0cf3313065153; __utmb=79960839.28.10.1749888108; jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1IjoiMTMwNjUxNTMiLCJpYXQiOjE3NDk4OTA2NzksImV4cCI6MTc0OTk3NzA3OX0.bfPkCvRMbzO0Wpx3W1GzqzDTWj3mFMX1lEX8xSYzRs8; FCNEC=%5B%5B%22AKsRol94amvT-sh5pLyQYesxeeqh1ANcAcZv1RruzC5qZWVCeTeRaIYxbKu_zBQ7aUm588xj0OtMrcuHk5D3YHJSRQvi47uuxqB0jkpAJJ9BoaRGHVxoB0ZDsmO0ivZYfN_Tg6ESvQl4AeyAVIW9MfScExiJNTOfGQ%3D%3D%22%5D%5D; _clsk=8eewh6%7C1749890696753%7C5%7C1%7Ci.clarity.ms%2Fcollect; _ga_R4TCZEVX9J=GS2.1.s1749890610$o1$g1$t1749890703$j33$l0$h0; _ga_KGL740D7XD=GS2.1.s1749888109$o2$g1$t1749890899$j60$l0$h2072563748'})

        # Start the periodic saving thread
        saving_thread = threading.Thread(target=periodic_save_task, args=(1,))
        saving_thread.daemon = True # Allow main program to exit even if thread is running
        saving_thread.start()

        try:
            current_page_url = Config.AUTO_RIA_START_URL
            while True:
                print(f"\nCollecting ad URLs from main page: {current_page_url}")
                ad_urls, next_page_url = collect_ad_urls_from_page(session, current_page_url)

                if ad_urls:
                    print(f"Found {len(ad_urls)} advertisements on this page. Processing...")
                    for i, ad_url in enumerate(ad_urls):
                        if ad_url in existing_ad_urls:
                            print(f"  [{i+1}/{len(ad_urls)}] Skipping already processed ad: {ad_url}")
                            continue # Skip to the next ad if already exists

                        print(f"  [{i+1}/{len(ad_urls)}] Processing ad: {ad_url}")
                        # Fetch ad page HTML for full parsing (including phones via API call)
                        ad_page_html = fetch_html_with_requests(session, ad_url)
                        if ad_page_html:
                            ad_data = parse_ad_page(ad_url, ad_page_html, session)
                            if ad_data:
                                print("    --- Advertisement Data ---")
                                for key, value in ad_data.items():
                                    print(f"    {key.replace('_', ' ').title()}: {value}")
                                print("    --------------------------")
                                with all_ads_data_lock:
                                    all_ads_data.append(ad_data)
                            else:
                                print(f"    Failed to parse advertisement data for {ad_url}.")
                        else:
                            print(f"    Failed to fetch ad page: {ad_url}")
                        time.sleep(0.5) # Small delay between ad page requests
                else:
                    print("No advertisement links found on this page. Stopping scraping.")
                    break # Break if no ads found on a page
                
                if next_page_url:
                    current_page_url = next_page_url
                    print(f"Navigating to next page: {current_page_url}")
                    time.sleep(2) # A longer delay before navigating to a new main page
                else:
                    print("No next page found. Stopping scraping.")
                    break # Exit loop if no next page
                
                # No general page delay here, as fetch_html_with_requests and pagination delays handle it.

        except KeyboardInterrupt:
            print("\nScraping stopped by user.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # Signal the saving thread to stop and wait for it to finish
            stop_saving_event.set()
            saving_thread.join()
            print("Saving thread stopped.")

            # Save any remaining data before exiting
            if all_ads_data:
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n--- [{current_time}] Saving {len(all_ads_data)} remaining ads to PostgreSQL ---")
                save_data_to_postgresql(all_ads_data)
                print(f"--- [{current_time}] Finished saving remaining ads ---")

            if all_ads_data:
                save_data_to_json(all_ads_data) # Save all collected data on exit
                # save_data_to_postgresql(all_ads_data) # This is now handled by periodic_save_task and remaining data save
            
            end_time = time.time()
            total_elapsed_time = end_time - start_time
            print(f"Total elapsed time: {total_elapsed_time:.2f} seconds")
