import psycopg2

def format_images(images):
    """Format a list of image URLs into a PostgreSQL array literal."""
    if images is not None and len(images) > 0:
        return '{' + ','.join(images) + '}'
    return '{}'

def insert_tweet(author_name, author_handle, profile_img_url, text, tweet_url, timestamp, metrics, images, conn):
    """Insert a tweet into the database."""
    formatted_images = format_images(images) 
    print("Inserting tweet with parameters:")
    print(f"Author Name: {author_name}")
    print(f"Author Handle: {author_handle}")
    print(f"Profile Image URL: {profile_img_url}")
    print(f"Text: {text}")
    print(f"Tweet URL: {tweet_url}")
    print(f"Timestamp: {timestamp}")
    print(f"Images: {formatted_images}") # Use the formatted images
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tweets (author_name, author_handle, profile_img_url, text, tweet_url, timestamp, images)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING tweet_id;  -- Ensure you are using the correct column name for the primary key
            """, (author_name, author_handle, profile_img_url, text, tweet_url, timestamp, formatted_images))

            tweet_id = cursor.fetchone()[0]
            conn.commit()
            print(f"Inserted tweet with ID: {tweet_id}")
            return tweet_id
    except Exception as e:
        print(f"Error inserting tweet: {str(e)}")
        conn.rollback()
        return None


def insert_reply(tweet_id, author_name, author_handle, profile_img_url, text, timestamp, metrics, images, conn):
    """Insert a reply into the database."""
    formatted_images = format_images(images)
    print("Inserting tweet with parameters:")
    print(f"Author Name: {author_name}")
    print(f"Author Handle: {author_handle}")
    print(f"Profile Image URL: {profile_img_url}")
    print(f"Text: {text}")
    print(f"Tweet URL: {tweet_url}")
    print(f"Timestamp: {timestamp}")
    print(f"Images: {formatted_images}")  # Use the formatted images
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO replies (tweet_id, author_name, author_handle, profile_img_url, text, timestamp, images)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (tweet_id, author_name, author_handle, profile_img_url, text, timestamp, formatted_images))  # Use formatted_images here

            conn.commit()
            print(f"Inserted reply for tweet ID: {tweet_id}")
    except Exception as e:
        print(f"Error inserting reply: {str(e)}")
        conn.rollback()


