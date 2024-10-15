from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import json
import random
from datetime import datetime
from config.db_config import connect_to_db
from db_operations.insert_operations import insert_tweet, insert_reply

conn = connect_to_db()

if conn is None:
    print("Database connection failed. Exiting.")
    exit()
else:
    print("Database connected.")

print("Connecting to browser...")

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Create the driver using ChromeDriverManager
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
print("Browser connected.")

# Specify the Twitter account and the date range for tweets
account_url = "https://x.com/FibeIndia"  # Example account
start_date = "2024-10-05"  # Format: YYYY-MM-DD
end_date = "2024-10-13"    # Format: YYYY-MM-DD

def is_within_date_range(tweet_date):
    """Check if tweet_date is within the specified range."""
    tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    
    is_within_range = start_date_obj <= tweet_date_obj <= end_date_obj
    print(f"Tweet Date: {tweet_date_obj}, Within Range: {is_within_range}")
    
    return is_within_range

def scroll_page():
    """Scroll down the timeline to load more tweets."""
    driver.execute_script("window.scrollBy(0, window.innerHeight);")
    time.sleep(random.uniform(5.0, 8.0))  # Pause to let content load

def collect_tweet_links():
    """Collect tweet URLs from the account page within the specified date range."""
    tweet_links = set()
    total_scrolls = 0
    max_scrolls = 50  # Adjust as needed to capture more tweets
    
    print("Navigating to account URL...")
    driver.get(account_url)

    print("Waiting for 2 minutes to log in...")
    time.sleep(120)  # Wait for login manually

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
    )
    
    while total_scrolls < max_scrolls:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tweets = soup.find_all("article", {"data-testid": "tweet"})
        for tweet in tweets:
            try:
                # Get tweet date
                time_element = tweet.find("time")
                if time_element:
                    tweet_date = time_element.get("datetime").split("T")[0]
                    
                    if tweet_date < start_date:
                        print(f"Reached tweets older than start date. Stopping collection.")
                        return list(tweet_links)

                    if is_within_date_range(tweet_date):
                        tweet_link_element = tweet.find("a", href=lambda href: href and "/status/" in href)
                        if tweet_link_element:
                            tweet_link = "https://x.com" + tweet_link_element['href']
                            tweet_links.add(tweet_link)

            except Exception as e:
                print(f"Error finding tweet URL: {e}")
                continue

        scroll_page()
        total_scrolls += 1

    print(f"Collected {len(tweet_links)} tweets within date range {start_date} to {end_date}.")
    return list(tweet_links)

def extract_tweet_data(tweet_element, tweet_link):
    """Extract data from a tweet element."""
    tweet_data = {'tweet_url': tweet_link}
    try:
        # Get author information
        author_element = tweet_element.find("div", {"data-testid": "User-Name"})
        if author_element:
            spans = author_element.find_all("span", recursive=True)
            for span in spans:
                text = span.get_text().strip()
                if text and not text.startswith("@"):
                    tweet_data["author_name"] = text
                    break
            handle_span = author_element.find("span", string=lambda text: text and text.startswith("@"))
            if handle_span:
                tweet_data["author_handle"] = handle_span.text.strip()

        # Get profile image
        profile_img_element = tweet_element.find("img", {"alt": lambda x: x and x.endswith("'s profile picture")})
        if profile_img_element:
            tweet_data["profile_img_url"] = profile_img_element['src']

        # Get tweet text
        text_element = tweet_element.find("div", {"data-testid": "tweetText"})
        if text_element:
            tweet_data["text"] = text_element.get_text(separator=' ').strip()

        # Get timestamp
        time_element = tweet_element.find("time")
        if time_element:
            tweet_data["timestamp"] = time_element.get("datetime")

        # Get tweet metrics
        metrics = {}
        for metric in ["reply", "retweet", "like"]:
            metric_element = tweet_element.find("div", {"data-testid": f"{metric}-count"})
            if metric_element:
                metrics[f"{metric}s"] = metric_element.text.strip()
        tweet_data["metrics"] = metrics

        # Get images
        image_elements = tweet_element.find_all("img", {"alt": "Image"})
        image_urls = [img['src'] for img in image_elements if img['src']]
        tweet_data["images"] = image_urls if image_urls else []

    except Exception as e:
        print(f"Error extracting tweet data: {str(e)}")

    return tweet_data

def scrape_replies(tweet_id, tweet_url, conn):
    """Scrape replies for a specific tweet and insert into database."""
    print(f"Scraping replies for tweet: {tweet_url}")
    
    try:
        driver.get(tweet_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
        )

        all_replies = []
        processed_tweets = set()

        def process_visible_replies():
            """Process all currently visible replies."""
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tweets = soup.find_all("article", {"data-testid": "tweet"})
            new_replies = 0
            for tweet in tweets[1:]:
                reply_data = {}
                tweet_text = tweet.get_text().strip()
                tweet_id_hash = hash(tweet_text[:100])

                if tweet_id_hash not in processed_tweets:
                    try:
                        author_element = tweet.find("div", {"data-testid": "User-Name"})
                        if author_element:
                            spans = author_element.find_all("span", recursive=True)
                            for span in spans:
                                text = span.get_text().strip()
                                if text and not text.startswith("@"):
                                    reply_data["author_name"] = text
                                    break
                            handle_span = author_element.find("span", string=lambda text: text and text.startswith("@"))
                            if handle_span:
                                reply_data["author_handle"] = handle_span.text.strip()

                        profile_img_element = tweet.find("div", {"data-testid": "Tweet-User-Avatar"}).find("img")
                        if profile_img_element:
                            reply_data["profile_img_url"] = profile_img_element['src']

                        text_element = tweet.find("div", {"data-testid": "tweetText"})
                        if text_element:
                            reply_data["text"] = text_element.get_text(separator=' ').strip()

                        time_element = tweet.find("time")
                        if time_element:
                            reply_data["timestamp"] = time_element.get("datetime")

                        metrics = {}
                        for metric in ["reply", "retweet", "like"]:
                            metric_element = tweet.find("div", {"data-testid": f"{metric}-count"})
                            if metric_element:
                                metrics[f"{metric}s"] = metric_element.text.strip()
                        reply_data["metrics"] = metrics

                        image_elements = tweet.find_all("img", {"alt": "Image"})
                        image_urls = [img['src'] for img in image_elements if img['src']]
                        reply_data["images"] = image_urls if image_urls else []

                        if reply_data.get("text"):
                            all_replies.append(reply_data)
                            processed_tweets.add(tweet_id_hash)
                            new_replies += 1

                    except Exception as e:
                        print(f"Error processing a reply: {str(e)}")
                        continue
            
            print(f"New replies added in this scroll: {new_replies}")
            return new_replies

        total_new_replies = process_visible_replies()
        while total_new_replies > 0:
            scroll_page()
            total_new_replies = process_visible_replies()

        print(f"Total replies collected: {len(all_replies)}")
        
        for reply in all_replies:
            try:
                insert_reply(
                    tweet_id=tweet_id,  # Pass the tweet_id to link reply
                    author_name=reply.get("author_name"),
                    author_handle=reply.get("author_handle"),
                    profile_img_url=reply.get("profile_img_url"),
                    text=reply.get("text"),
                    timestamp=reply.get("timestamp"),
                    metrics=json.dumps(reply.get("metrics")),
                    images=json.dumps(reply.get("images")),
                    conn=conn
                )
            except Exception as e:
                print(f"Error inserting reply into database: {str(e)}")
    
    except Exception as e:
        print(f"Error loading tweet page: {str(e)}")

def scrape_tweets_and_replies():
    """Main function to scrape tweets and their replies."""
    tweet_links = collect_tweet_links()
    
    for tweet_link in tweet_links:
        try:
            driver.get(tweet_link)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tweet_element = soup.find("article", {"data-testid": "tweet"})
            tweet_data = extract_tweet_data(tweet_element, tweet_link)
            if tweet_data.get("text"):
                tweet_id = insert_tweet(
                    author_name=tweet_data.get("author_name"),
                    author_handle=tweet_data.get("author_handle"),
                    profile_img_url=tweet_data.get("profile_img_url"),
                    text=tweet_data.get("text"),
                    tweet_url=tweet_data.get("tweet_url"),
                    timestamp=tweet_data.get("timestamp"),
                    metrics=json.dumps(tweet_data.get("metrics")),
                    images=json.dumps(tweet_data.get("images")),
                    conn=conn
                )
                if tweet_id:  # Scrape replies only if tweet insertion is successful
                    scrape_replies(tweet_id, tweet_data.get("tweet_url"), conn)
        
        except Exception as e:
            print(f"Error scraping tweet: {str(e)}")

# Start the scraping process
scrape_tweets_and_replies()

# Close the browser and database connection
driver.quit()
conn.close()
