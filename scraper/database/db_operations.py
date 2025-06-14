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

def get_table_columns(conn):
    """Get existing columns in auto_ria_ads table"""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'auto_ria_ads' 
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        return {col[0]: col[1] for col in columns}
    except Exception as e:
        print(f"Error getting table columns: {e}")
        return {}

def save_data_to_postgresql(all_ads_data):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            
            # First, check existing table structure
            existing_columns = get_table_columns(conn)
            print(f"Existing table columns: {list(existing_columns.keys())}")
            
            # Create table if not exists with new structure
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
            
            # Check if we have old column names and need to migrate or use them
            has_old_columns = any(col in existing_columns for col in ['price', 'mileage', 'seller_name', 'phones'])
            has_new_columns = any(col in existing_columns for col in ['price_usd', 'odometer', 'username', 'phone_number'])
            
            if has_old_columns and not has_new_columns:
                print("Detected old column structure. Adding new columns...")
                # Add new columns alongside old ones
                columns_to_add = [
                    ("price_usd", "INTEGER"),
                    ("odometer", "INTEGER"), 
                    ("username", "TEXT"),
                    ("phone_number", "BIGINT"),
                    ("images_count", "INTEGER"),
                    ("car_number", "TEXT"),
                    ("car_vin", "TEXT")
                ]
                
                for column_name, column_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE auto_ria_ads ADD COLUMN IF NOT EXISTS {column_name} {column_type};")
                        conn.commit()
                        print(f"Added {column_name} column to auto_ria_ads table.")
                    except Exception as e:
                        print(f"Warning: Could not add {column_name} column: {e}")
            
            # Ensure datetime_found column exists
            try:
                cur.execute("ALTER TABLE auto_ria_ads ADD COLUMN IF NOT EXISTS datetime_found TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;")
                conn.commit()
                print("Ensured datetime_found column exists in auto_ria_ads table.")
            except Exception as e:
                print(f"Warning: Could not add datetime_found column: {e}")

            conn.commit()

            # Get updated column list
            existing_columns = get_table_columns(conn)
            
            for ad_data in all_ads_data:
                current_timestamp = datetime.datetime.now()
                
                # Determine which column names to use based on what exists
                if 'price_usd' in existing_columns:
                    # Use new column names
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
                        ad_data.get('phone_number'),
                        ad_data.get('image_url'),
                        ad_data.get('images_count'),
                        ad_data.get('car_number'),
                        ad_data.get('car_vin'),
                        current_timestamp
                    ))
                else:
                    # Fallback to old column names if new ones don't exist
                    print("Using old column structure for compatibility")
                    # Convert phone_number to string for old phones column
                    phone_str = str(ad_data.get('phone_number')) if ad_data.get('phone_number') else None
                    
                    cur.execute("""
                        INSERT INTO auto_ria_ads (
                            url, title, price, mileage, seller_name, phones, image_url, total_photos, license_plate, vin, datetime_found
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO UPDATE SET
                            title = EXCLUDED.title,
                            price = EXCLUDED.price,
                            mileage = EXCLUDED.mileage,
                            seller_name = EXCLUDED.seller_name,
                            phones = EXCLUDED.phones,
                            image_url = EXCLUDED.image_url,
                            total_photos = EXCLUDED.total_photos,
                            license_plate = EXCLUDED.license_plate,
                            vin = EXCLUDED.vin,
                            datetime_found = EXCLUDED.datetime_found;
                    """, (
                        ad_data.get('url'),
                        ad_data.get('title'),
                        ad_data.get('price_usd'),  # Map price_usd to price
                        ad_data.get('odometer'),   # Map odometer to mileage
                        ad_data.get('username'),   # Map username to seller_name
                        phone_str,                 # Map phone_number to phones
                        ad_data.get('image_url'),
                        ad_data.get('images_count'), # Map images_count to total_photos
                        ad_data.get('car_number'),   # Map car_number to license_plate
                        ad_data.get('car_vin'),      # Map car_vin to vin
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