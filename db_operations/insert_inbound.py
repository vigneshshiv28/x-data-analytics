import json
import logging
from config.db_config import connect_to_db

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def insert_conversation_into_db(tweet_id, author_name, author_handle, conversation):
    """Insert tweet conversation into the database."""
    conn = connect_to_db()
    if conn is None:
        logging.error("Database connection failed. Insert operation aborted.")
        return

    try:
        cur = conn.cursor()
        
        # Convert conversation into JSON format
        conversation_json = json.dumps(conversation)

        # Insert query
        cur.execute("""
            INSERT INTO cases (tweet_id, author_name, author_handle, conversation)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tweet_id) DO NOTHING;
        """, (tweet_id, author_name, author_handle, conversation_json))
        
        # Commit transaction
        conn.commit()
        logging.info(f"Inserted tweet {tweet_id} into the database.")

    except Exception as e:
        logging.error(f"Error inserting tweet {tweet_id} into the database: {e}")
        if conn:
            conn.rollback()
    finally:
        # Close the cursor and connection in the finally block to ensure they are closed even if an error occurs
        if cur:
            cur.close()
        if conn:
            conn.close()
