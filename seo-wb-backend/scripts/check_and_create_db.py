import psycopg
from psycopg import sql

db_url = "postgresql://postgres:12345678@127.0.0.1:5432/postgres"
target_db = "seo_wb_db"

try:
    # Connect to the default postgres database
    conn = psycopg.connect(db_url, autocommit=True)
    with conn.cursor() as cur:
        # Check if seo_wb_db exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        exists = cur.fetchone()
        if not exists:
            print(f"Database {target_db} does not exist. Creating...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
            print(f"Database {target_db} created successfully.")
        else:
            print(f"Database {target_db} already exists.")
    conn.close()
except Exception as e:
    print(f"Error checking/creating database: {e}")
