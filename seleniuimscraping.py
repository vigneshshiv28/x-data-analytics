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
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

account_url = "https://x.com/FibeIndia/with_replies"
start_date = "2024-10-05"
end_date = "2024-10-18"

company_handle = "FibeIndia"

def is_within_date_range(tweet_date):
    tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    return start_date_obj <= tweet_date_obj <= end_date_obj

def scroll_page():
    driver.execute_script("window.scrollBy(0, window.innerHeight);")
    time.sleep(2)

def collect_customer_tweets():
    customer_tweet_links = set()
    total_scrolls = 0
    max_scrolls = 50
    
    driver.get(account_url)
    logging.info("Waiting for manual login...")
    time.sleep(120)  # Manually log in during this time
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
    )
    
    processed_tweets = set()
    
    while total_scrolls < max_scrolls:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tweets = soup.find_all("article", {"data-testid": "tweet"})
        
        new_tweets = 0
        for tweet in tweets:
            try:
                tweet_text = tweet.get_text().strip()
                tweet_id_hash = hash(tweet_text[:100])
                
                if tweet_id_hash not in processed_tweets:
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
                                    new_tweets += 1
                                    logging.info(f"Added new tweet: {tweet_link}")
                    
                    processed_tweets.add(tweet_id_hash)
            
            except Exception as e:
                logging.error(f"Error processing tweet: {e}")
                continue
        
        scroll_page()
        total_scrolls += 1
        logging.info(f"Scrolled {total_scrolls} times. Added {new_tweets} new tweets. Total collected: {len(customer_tweet_links)}")

        if new_tweets == 0:
            logging.info("No new tweets found. Stopping collection.")
            break

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
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tweets = soup.find_all("article", {"data-testid": "tweet"})
            new_replies = 0

            for tweet in tweets:
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
                        image_urls = [img['src'] for img in image_elements if img.get('src')]
                        reply_data["images"] = image_urls

                        if reply_data.get("author_handle") == f"@{company_handle}":
                            reply_data["type"] = "company_response"
                        else:
                            reply_data["type"] = "customer_tweet"

                        conversation.append(reply_data)
                        processed_tweets.add(tweet_id_hash)
                        new_replies += 1

                    except Exception as e:
                        logging.error(f"Error processing a reply: {str(e)}")
                        continue
            
            logging.info(f"New replies added in this scroll: {new_replies}")
            return new_replies

        total_new_replies = process_visible_replies()
        while total_new_replies > 0:
            scroll_page()
            total_new_replies = process_visible_replies()

        logging.info(f"Finished scraping conversation. Total replies: {len(conversation)}")
        
        conversation_json = json.dumps(conversation, indent=4)
        return conversation_json
    
    except Exception as e:
        logging.error(f"Error loading conversation for tweet {tweet_url}: {str(e)}")
        return None

# Main execution
customer_tweets = collect_customer_tweets()
all_conversations = []

for i, tweet_url in enumerate(customer_tweets, 1):
    logging.info(f"Processing tweet {i} of {len(customer_tweets)}")
    conversation_json = scrape_conversations(tweet_url)
    if conversation_json:
        all_conversations.append(json.loads(conversation_json))
    
    # Save progress after each conversation
    with open('customer_complaints_and_responses_progress.json', 'w') as f:
        json.dump(all_conversations, f, indent=4)
    logging.info(f"Saved progress. Processed {i} tweets so far.")

# Save all conversations to a final JSON file
with open('customer_complaints_and_responses_final.json', 'w') as f:
    json.dump(all_conversations, f, indent=4)

logging.info("All conversations have been saved to 'customer_complaints_and_responses_final.json'")
driver.quit()