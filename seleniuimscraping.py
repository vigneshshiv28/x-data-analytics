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
    # Convert strings to datetime objects for comparison
    tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Compare datetime objects
    is_within_range = start_date_obj <= tweet_date_obj <= end_date_obj
    
    # Log the comparison result
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
        print("tweet")
        print(tweets)
        for tweet in tweets:
            try:
                # Get tweet date
                time_element = tweet.find("time")
                print("time element")
                print(time_element)
                if time_element:
                    tweet_date = time_element.get("datetime").split("T")[0]  # Get only date part
                    print("tweet date")
                    print(tweet_date)
                    # Check if tweet is older than start date
                    if tweet_date < start_date:
                        print(f"Reached tweets older than start date. Stopping collection.")
                        return list(tweet_links)

                    # Check if tweet is within the specified date range
                    if is_within_date_range(tweet_date):
                        # Extract the tweet link using the anchor tag with href containing '/status/'
                        tweet_link_element = tweet.find("a", href=lambda href: href and "/status/" in href)
                        print("tweet link")
                        print(tweet_link_element)
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



def extract_tweet_data(tweet_element):
    """Extract data from a tweet element."""
    tweet_data = {}
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

def scrape_replies(tweet_url):
    """Scrape replies for a specific tweet."""
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
                tweet_id = hash(tweet_text[:100])

                if tweet_id not in processed_tweets:
                    try:
                        # Get author information
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

                        # Get profile image
                        profile_img_element = tweet.find("div", {"data-testid": "Tweet-User-Avatar"}).find("img")
                        if profile_img_element:
                            reply_data["profile_img_url"] = profile_img_element['src']

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

                        # Get images
                        image_elements = tweet.find_all("img", {"alt": "Image"})
                        image_urls = [img['src'] for img in image_elements if img['src']]
                        reply_data["images"] = image_urls if image_urls else []

                        if reply_data.get("text"):
                            all_replies.append(reply_data)
                            processed_tweets.add(tweet_id)
                            new_replies += 1

                    except Exception as e:
                        print(f"Error processing a reply: {str(e)}")
                        continue
            
            return new_replies

        def scroll_and_collect_replies():
            """Scroll and collect all replies for the tweet."""
            no_new_replies_count = 0
            total_scrolls = 0
            max_scrolls = 50

            while total_scrolls < max_scrolls and no_new_replies_count < 5:
                new_replies = process_visible_replies()
                if new_replies > 0:
                    print(f"Found {new_replies} new replies.")
                    no_new_replies_count = 0
                else:
                    no_new_replies_count += 1

                scroll_page()
                total_scrolls += 1

            return all_replies

        # Collect replies
        replies = scroll_and_collect_replies()
        return replies

    except Exception as e:
        print(f"An error occurred while scraping replies: {e}")
        return []

# Main script
try:
    tweet_links = collect_tweet_links()
    print(f"Collected {len(tweet_links)} tweet links.")
    
    all_data = []
    for tweet_url in tweet_links:
        print(f"Processing tweet: {tweet_url}")
        # Scrape the main tweet and its replies
        replies = scrape_replies(tweet_url)
        all_data.append({
            "tweet_url": tweet_url,
            "replies": replies
        })

    # Save the scraped data to a JSON file
    with open('twitter_data_by_date_range.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print("Data saved to 'twitter_data_by_date_range.json'")

except Exception as e:
    print(f"An error occurred: {e}")
    
finally:
    print("Closing browser.")
    driver.quit()

