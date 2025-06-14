import psycopg2
from scraper.database.db_operations import connect_db

def clear_all_data_from_db():
    """Deletes all data from the auto_ria_ads table in the PostgreSQL database."""
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("TRUNCATE TABLE auto_ria_ads RESTART IDENTITY;") # RESTART IDENTITY resets the ID sequence
            conn.commit()
            print("All data successfully cleared from auto_ria_ads table.")
        except Exception as e:
            print(f"Error clearing data from auto_ria_ads table: {e}")
        finally:
            if conn:
                cur.close()
                conn.close()
    else:
        print("Failed to connect to the database. Could not clear data.") 