import psycopg2

def connect_to_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname="",
            user="",
            password="",
            host="",
            port=""
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None