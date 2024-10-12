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
from selenium.webdriver.common.keys import Keys
import random

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

# URL for the specific tweet
post_url = "https://x.com/FibeIndia/status/1839638840983892292"

try:
    print("Navigating to URL...")
    driver.get(post_url)
    print("URL loaded successfully.")

    print("Waiting for 2 minutes to log in...")
    time.sleep(120)  # Wait for login

    # Wait for replies to load
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
    )
    print("Tweet content detected.")

    # Initialize list to store replies and track processed tweets
    all_replies = []
    processed_tweets = set()

    def scroll_page():
        """Scroll the page with random intervals and distances"""
        scroll_amount = random.randint(300, 700)  # Random scroll distance
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(1.5, 3.0))  # Random wait time

    def process_visible_replies():
        """Process all currently visible replies"""
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tweets = soup.find_all("article", {"data-testid": "tweet"})
        
        new_replies = 0
        for tweet in tweets[1:]:  # Skip the first tweet (main tweet)
            # Create a unique identifier for the tweet
            tweet_text = tweet.get_text().strip()
            tweet_id = hash(tweet_text[:100])  # Use first 100 chars as identifier
            
            if tweet_id not in processed_tweets:
                reply_data = {}
                try:
                    # Get reply author information
                    author_element = tweet.find("div", {"data-testid": "User-Name"})
                    if author_element:
                        spans = author_element.find_all("span", recursive=True)
                        for span in spans:
                            text = span.get_text().strip()
                            if text and not text.startswith("@"):
                                reply_data["author_name"] = text
                                break
                        
                        # Get username/handle
                        handle_span = author_element.find("span", string=lambda text: text and text.startswith("@"))
                        if handle_span:
                            reply_data["author_handle"] = handle_span.text.strip()

                    # Get reply text
                    text_element = tweet.find("div", {"data-testid": "tweetText"})
                    if text_element:
                        reply_data["text"] = text_element.get_text(separator=' ').strip()
                    
                    # Get timestamp
                    time_element = tweet.find("time")
                    if time_element:
                        reply_data["timestamp"] = time_element.get("datetime")

                    # Get reply metrics
                    metrics = {}
                    for metric in ["reply", "retweet", "like"]:
                        metric_element = tweet.find("div", {"data-testid": f"{metric}-count"})
                        if metric_element:
                            metrics[f"{metric}s"] = metric_element.text.strip()
                    reply_data["metrics"] = metrics

                    if reply_data.get("text"):  # Only add if we have at least the text
                        all_replies.append(reply_data)
                        processed_tweets.add(tweet_id)
                        new_replies += 1

                except Exception as e:
                    print(f"Error processing a reply: {str(e)}")
                    continue
        
        return new_replies

    print("\nScrolling and capturing replies...")
    no_new_replies_count = 0
    total_scrolls = 0
    max_scrolls = 200  # Increased maximum scrolls

    while total_scrolls < max_scrolls and no_new_replies_count < 5:
        # Process current visible replies
        new_replies = process_visible_replies()
        
        if new_replies > 0:
            print(f"Found {new_replies} new replies. Total replies so far: {len(all_replies)}")
            no_new_replies_count = 0
        else:
            no_new_replies_count += 1

        # Scroll the page
        previous_height = driver.execute_script("return document.body.scrollHeight")
        scroll_page()
        
        # Wait for new content to load
        time.sleep(2)
        
        # Check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == previous_height:
            # Try one more aggressive scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            if new_height == driver.execute_script("return document.body.scrollHeight"):
                if no_new_replies_count >= 5:
                    print("Reached the end of replies.")
                    break
        
        total_scrolls += 1
        
        # Occasionally scroll up a bit to trigger more loading
        if total_scrolls % 10 == 0:
            driver.execute_script("window.scrollBy(0, -500);")
            time.sleep(1.5)

    print(f"\nFinished capturing replies. Total replies found: {len(all_replies)}")
    
    # Save replies to file
    output = {
        "tweet_url": post_url,
        "replies_count": len(all_replies),
        "replies": all_replies
    }
    
    with open('twitter_replies.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Replies saved to 'twitter_replies.json'")

    # Print sample of replies
    print("\nSample of first 3 replies:")
    for i, reply in enumerate(all_replies[:3]):
        print(f"\nReply {i+1}:")
        print(f"Author: {reply.get('author_name', 'N/A')} ({reply.get('author_handle', 'N/A')})")
        print(f"Text: {reply.get('text', 'N/A')[:100]}...")
        print(f"Metrics: {reply.get('metrics', {})}")

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    print("\nClosing browser.")
    driver.quit()