import psycopg2
import os
from scraper.config import Config
import datetime


def connect_db():
    conn = None
    try:
        print(f"Attempting to connect to PostgreSQL at: {Config.PG_HOST}:{Config.PG_PORT}, DB: {Config.PG_DBNAME}, User: {Config.PG_USER}")
        conn = psycopg2.connect(
            host=Config.PG_HOST,
            database=Config.PG_DBNAME,
            user=Config.PG_USER,
            password=Config.PG_PASSWORD,
            port=Config.PG_PORT
        )
        print("Successfully connected to PostgreSQL database.")
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

def save_data_to_postgresql(all_ads_data):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS auto_ria_ads (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    price_usd INTEGER,
                    odometer INTEGER,
                    username TEXT,
                    phone_number BIGINT,
                    image_url TEXT,
                    images_count INTEGER,
                    car_number TEXT,
                    car_vin TEXT,
                    datetime_found TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """
            )
            
            # Add datetime_found column if it doesn't exist (for existing tables)
            try:
                cur.execute("ALTER TABLE auto_ria_ads ADD COLUMN IF NOT EXISTS datetime_found TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;")
                conn.commit()
                print("Ensured datetime_found column exists in auto_ria_ads table.")
            except Exception as e:
                # This specific error might occur if the column already exists, but IF NOT EXISTS should prevent it.
                # Catching generic Exception for robustness.
                print(f"Warning: Could not add datetime_found column (might already exist or another issue): {e}")

            conn.commit()

            for ad_data in all_ads_data:
                # No need for quoted_phones or phones_array anymore as phone_number is BIGINT
                # phones_array = '{}'.format(','.join([f'"{p.replace('"', '""')}' for p in ad_data['phones']])) if ad_data['phones'] else None
                
                current_timestamp = datetime.datetime.now()

                cur.execute("""
                    INSERT INTO auto_ria_ads (
                        url, title, price_usd, odometer, username, phone_number, image_url, images_count, car_number, car_vin, datetime_found
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        price_usd = EXCLUDED.price_usd,
                        odometer = EXCLUDED.odometer,
                        username = EXCLUDED.username,
                        phone_number = EXCLUDED.phone_number,
                        image_url = EXCLUDED.image_url,
                        images_count = EXCLUDED.images_count,
                        car_number = EXCLUDED.car_number,
                        car_vin = EXCLUDED.car_vin,
                        datetime_found = EXCLUDED.datetime_found;
                """, (
                    ad_data.get('url'),
                    ad_data.get('title'),
                    ad_data.get('price_usd'),
                    ad_data.get('odometer'),
                    ad_data.get('username'),
                    ad_data.get('phone_number'), # Pass the phone_number directly (should be BIGINT or None)
                    ad_data.get('image_url'),
                    ad_data.get('images_count'),
                    ad_data.get('car_number'),
                    ad_data.get('car_vin'),
                    current_timestamp
                ))
            conn.commit()
            print(f"Successfully saved {len(all_ads_data)} advertisements to PostgreSQL.")
        except Exception as e:
            print(f"Error saving data to PostgreSQL: {e}")
        finally:
            if conn:
                cur.close()
                conn.close()
    else:
        print("Skipping PostgreSQL save due to connection error.")

def get_existing_ad_urls():
    conn = connect_db()
    existing_urls = set()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT url FROM auto_ria_ads;")
            for row in cur.fetchall():
                existing_urls.add(row[0])
            print(f"Loaded {len(existing_urls)} existing ad URLs from PostgreSQL.")
        except Exception as e:
            print(f"Error fetching existing URLs from PostgreSQL: {e}")
        finally:
            if conn:
                cur.close()
                conn.close()
    return existing_urls 