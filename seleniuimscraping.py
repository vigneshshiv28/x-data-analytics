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
    time.sleep(120)  # Wait for login manually

    # Wait for replies to load
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
    )
    print("Tweet content detected.")

    # Initialize list to store replies and track processed tweets
    all_replies = []
    processed_tweets = set()

    def scroll_page():
        """Scroll by a constant distance based on the initial scrollable height."""
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(random.uniform(5.0, 8.0))  # Pause to let content load

    def process_visible_replies():
        """Process all currently visible replies."""
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tweets = soup.find_all("article", {"data-testid": "tweet"})

        new_replies = 0
        for tweet in tweets[1:]:  # Skip the first tweet (main tweet)
            reply_data = {}
            tweet_text = tweet.get_text().strip()
            tweet_id = hash(tweet_text[:100])  # Use first 100 chars as identifier
            
            if tweet_id not in processed_tweets:
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

                    # Get profile image URL
                    profile_img_element = tweet.find("div", {"data-testid": "Tweet-User-Avatar"}).find("img")
                    if profile_img_element:
                        reply_data["profile_img_url"] = profile_img_element['src']
                    else:
                        reply_data["profile_img_url"] = ""  # Empty string if no profile image

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

                    # Scrape image URL from tweet, if available
                    image_elements = tweet.find_all("img", {"alt": "Image"})
                    image_urls = [img['src'] for img in image_elements if img['src']]
                    reply_data["images"] = image_urls if image_urls else []

                    if reply_data.get("text"):  # Only add if we have at least the text
                        all_replies.append(reply_data)
                        processed_tweets.add(tweet_id)
                        new_replies += 1

                except Exception as e:
                    print(f"Error processing a reply: {str(e)}")
                    continue
        
        return new_replies

    def click_show_more_replies():
        """Click 'Show more replies' if available"""
        try:
            show_more_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//button//span[text()='Show']"))
            )
            if show_more_button:
                driver.execute_script("arguments[0].scrollIntoView();", show_more_button)  # Scroll to button
                show_more_button.click()
                time.sleep(3)  # Allow time for replies to load

        except Exception as e:
            print(f"Error clicking 'Show more replies': {e}")

    print("\nScrolling and capturing replies...")
    no_new_replies_count = 0
    total_scrolls = 0
    max_scrolls = 300  # Increased maximum scrolls

    while total_scrolls < max_scrolls and no_new_replies_count < 5:
        # Process current visible replies
        new_replies = process_visible_replies()

        if new_replies > 0:
            print(f"Found {new_replies} new replies. Total replies so far: {len(all_replies)}")
            no_new_replies_count = 0
        else:
            no_new_replies_count += 1

        # Scroll the page
        scroll_page()

        # Click 'Show more replies' if available
        click_show_more_replies()

        total_scrolls += 1

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

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    print("\nClosing browser.")
    driver.quit()
