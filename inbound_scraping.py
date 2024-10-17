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

        # Check if we've reached the end of the page
        if total_scrolls > 1 and len(customer_tweet_links) == prev_tweet_count:
            logging.info("Reached end of page or no new tweets found. Stopping collection.")
            break
        prev_tweet_count = len(customer_tweet_links)

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
        
        def process_replies():
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tweets = soup.find_all("article", {"data-testid": "tweet"})
            replies = []

            for tweet in tweets:
                reply_data = {}
                
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

                    text_element = tweet.find("div", {"data-testid": "tweetText"})
                    if text_element:
                        reply_data["text"] = text_element.get_text(separator=' ').strip()

                    time_element = tweet.find("time")
                    if time_element:
                        reply_data["timestamp"] = time_element.get("datetime")

                    if reply_data.get("author_handle") == f"@{company_handle}":
                        reply_data["type"] = "company_response"
                    else:
                        reply_data["type"] = "customer_tweet"

                    replies.append(reply_data)

                except Exception as e:
                    logging.error(f"Error processing reply: {str(e)}")
                    continue

            return replies

        conversation.extend(process_replies())
        
        while True:
            scroll_page()
            previous_length = len(conversation)
            new_replies = process_replies()
            conversation.extend(new_replies)
            
            if len(conversation) == previous_length:
                # Check for "Show more replies" button
                try:
                    show_more_button = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Show more replies')]"))
                    )
                    show_more_button.click()
                    logging.info("Clicked 'Show more replies' button.")
                    time.sleep(2)
                except (NoSuchElementException, TimeoutException):
                    logging.info("No 'Show more replies' button found or reached end of conversation.")
                    break
            
            logging.info(f"Processed {len(new_replies)} new replies. Total replies: {len(conversation)}")

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