from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import logging
import csv
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Selenium WebDriver setup
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

account_url = "https://x.com/FibeIndia/with_replies"
start_date = "2023-01-01"
end_date = "2024-10-19"
company_handle = "FibeIndia"

def is_within_date_range(tweet_date):
    tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    return start_date_obj <= tweet_date_obj <= end_date_obj

def scroll_page():
    driver.execute_script("window.scrollBy(0, window.innerHeight)/4;")
    time.sleep(5)

def extract_count_by_testid(tweet, testid):
    # Find the button with the 'data-testid' attribute
    button = tweet.find('button', {'data-testid': testid})
    if button:
        # Extract the text from the corresponding span
        span = button.find('span', class_='css-1jxf684')
        if span:
            count = span.get_text()
            return int(count) if count.isdigit() else 0
    return 0

def collect_customer_tweets():
    customer_tweet_links = set()
    total_scrolls = 0
    max_scrolls = 500
    
    driver.get(account_url)
    logging.info("Waiting for manual login...")
    time.sleep(120)  # Allow for manual login
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
    )
    
    while total_scrolls < max_scrolls:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tweets = soup.find_all("article", {"data-testid": "tweet"})
        
        for tweet in tweets:
            try:
                time_element = tweet.find("time")
                if time_element:
                    tweet_date = time_element.get("datetime").split("T")[0]
                    
                    if tweet_date < start_date:
                        logging.info(f"Reached tweets before start date. Collected {len(customer_tweet_links)} tweets.")
                        return list(customer_tweet_links)

                    if is_within_date_range(tweet_date):
                        author_handle_element = tweet.find("a", href=lambda href: href and "/status/" in href)
                        
                        if author_handle_element and company_handle not in author_handle_element.get('href'):
                            tweet_link = "https://x.com" + author_handle_element['href']
                            if tweet_link not in customer_tweet_links:
                                customer_tweet_links.add(tweet_link)
                                logging.info(f"Added new tweet: {tweet_link}")
            
            except Exception as e:
                logging.error(f"Error finding tweet URL: {e}")
                continue
        
        scroll_page()
        total_scrolls += 1
        logging.info(f"Scrolled {total_scrolls} times. Collected {len(customer_tweet_links)} tweets so far.")
        
    logging.info(f"Finished collecting tweets. Total collected: {len(customer_tweet_links)}")
    return list(customer_tweet_links)

def scrape_conversations(tweet_url):
    conversation = []
    driver.get(tweet_url)
    logging.info(f"Scraping conversation for tweet: {tweet_url}")
    
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
        )

        processed_tweets = set()

        def process_visible_replies():
            """Process all currently visible replies."""
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tweets = soup.find_all("article", {"data-testid": "tweet"})
            new_replies = 0

            for tweet in tweets:  # Skipping the first tweet (original post)
                reply_data = {}
                tweet_text = tweet.get_text().strip()
                tweet_id_hash = hash(tweet_text[:100])

                if tweet_id_hash not in processed_tweets:
                    try:
                        # Extracting author name and handle
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

                        # Extracting tweet content (text)
                        text_element = tweet.find("div", {"data-testid": "tweetText"})
                        if text_element:
                            reply_data["text"] = text_element.get_text(separator=' ').strip()

                        # Extracting timestamp
                        time_element = tweet.find("time")
                        if time_element:
                            reply_data["timestamp"] = time_element.get("datetime")
                        
                        # Extracting likes, retweets, replies
                        reply_data["likes"] = extract_count_by_testid(tweet, "like")
                        reply_data["retweets"] = extract_count_by_testid(tweet, "retweet")
                        reply_data["replies"] = extract_count_by_testid(tweet, "reply")

                        # Extracting image URL if available
                        img_element = tweet.find("img", {"alt": "Image"})
                        if img_element:
                            reply_data["image_url"] = img_element["src"]
                        else:
                            reply_data["image_url"] = None

                        # Extracting tweet link
                        reply_data["tweet_link"] = tweet_url

                        # Check if the author is the company
                        if reply_data.get("author_handle") == f"@{company_handle}":
                            continue  # Skip company's replies

                        conversation.append(reply_data)
                        processed_tweets.add(tweet_id_hash)
                        new_replies += 1

                    except Exception as e:
                        logging.error(f"Error processing a reply: {str(e)}")
                        continue

            return new_replies

        # Initial scrape
        total_new_replies = process_visible_replies()

        # Scroll and process more replies if available
        while total_new_replies > 0:
            scroll_page()
            total_new_replies = process_visible_replies()

        logging.info(f"Total replies collected: {len(conversation)}")
        return conversation

    except Exception as e:
        logging.error(f"Error loading conversation for tweet {tweet_url}: {str(e)}")
        return None

def save_tweets_to_csv(conversations, filename):
    """Save the tweets and their properties to a CSV file."""
    if not os.path.exists('tweets'):
        os.makedirs('tweets')

    csv_path = os.path.join('tweets', filename)

    # Write to CSV
    with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["tweet_id", "author_name", "author_handle", "text", "timestamp", "likes", "retweets", "replies", "image_url", "tweet_link"])
        writer.writeheader()

        for conversation in conversations:
            for tweet in conversation:
                writer.writerow(tweet)

    logging.info(f"Saved tweets to {csv_path}")

# Main execution
customer_tweets = collect_customer_tweets()
all_tweets = []

for i, tweet_url in enumerate(customer_tweets, 1):
    logging.info(f"Processing tweet {i} of {len(customer_tweets)}")
    
    conversation = scrape_conversations(tweet_url)
    if conversation:
        all_tweets.append(conversation)

# Save all tweets to a CSV file
save_tweets_to_csv(all_tweets, "fibe_India_tweets.csv")

logging.info("All tweets have been saved to the CSV file.")
driver.quit()
