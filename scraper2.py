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
import json
import signal
import sys
import threading
from threading import Lock
import queue

# Set up logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

class TwitterScraper(threading.Thread):
    # Class-level lock for thread-safe logging
    log_lock = Lock()
    
    def __init__(self, account_info):
        super().__init__()
        self.account_url = f"https://x.com/{account_info['handle']}/with_replies"
        self.start_date = account_info.get('start_date', "2023-10-24")
        self.end_date = account_info.get('end_date', "2024-10-24")
        self.company_handle = account_info['handle']
        self.tweet_data = []
        self.checkpoint_file = f"33tweet_checkpoint_{self.company_handle}.json"
        self.processed_tweets = set()
        self.driver = None
        self._stop_event = threading.Event()

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def safe_log(self, level, message):
        """Thread-safe logging"""
        with self.log_lock:
            if level == "INFO":
                logging.info(f"[{self.company_handle}] {message}")
            elif level == "ERROR":
                logging.error(f"[{self.company_handle}] {message}")

    def load_checkpoint(self):
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    self.tweet_data = checkpoint_data['tweet_data']
                    self.processed_tweets = set(checkpoint_data['processed_tweets'])
                self.safe_log("INFO", f"Loaded {len(self.tweet_data)} tweets from checkpoint")
                return True
        except Exception as e:
            self.safe_log("ERROR", f"Error loading checkpoint: {str(e)}")
        return False

    def save_checkpoint(self):
        try:
            checkpoint_data = {
                'tweet_data': self.tweet_data,
                'processed_tweets': list(self.processed_tweets),
                'timestamp': datetime.now().isoformat()
            }
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            self.safe_log("INFO", f"Saved checkpoint with {len(self.tweet_data)} tweets")
        except Exception as e:
            self.safe_log("ERROR", f"Error saving checkpoint: {str(e)}")

    # [Previous methods remain the same, just update logging to use safe_log]
    # ... [extract_tweet_id, extract_count_by_testid, extract_tweet_data, is_within_date_range remain unchanged] ...

    def scroll_page(self):
        try:
            last_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            
            for _ in range(8):
                if self.stopped():
                    return False
                self.driver.execute_script("window.scrollBy(0, window.innerHeight / 4);")
                time.sleep(0.5)
            
            new_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            return new_height != last_height
            
        except Exception as e:
            self.safe_log("ERROR", f"Error scrolling page: {str(e)}")
            return False

    def collect_tweets(self):
        total_scrolls = 0
        max_scrolls = 2500
        checkpoint_frequency = 20
        
        try:
            self.driver.get(self.account_url)
            self.safe_log("INFO", "Waiting for manual login...")
            time.sleep(120)  # Allow time for manual login
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
            )
            
            self.load_checkpoint()
            
            while total_scrolls < max_scrolls and not self.stopped():
                try:
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    tweets = soup.find_all("article", {"data-testid": "tweet"})
                    
                    new_tweets_found = False
                    for tweet in tweets:
                        if self.stopped():
                            break

                        try:
                            time_element = tweet.find("time")
                            if not time_element:
                                continue
                                
                            tweet_date = time_element.get("datetime")
                            if not self.is_within_date_range(tweet_date):
                                continue

                            tweet_data = self.extract_tweet_data(tweet)
                            if not tweet_data or not tweet_data["tweet_id"]:
                                continue

                            if tweet_data["tweet_id"] in self.processed_tweets:
                                continue

                            if tweet_data["author_handle"] == f"@{self.company_handle}":
                                continue

                            self.tweet_data.append(tweet_data)
                            self.processed_tweets.add(tweet_data["tweet_id"])
                            new_tweets_found = True
                            
                            self.safe_log("INFO", f"Added new tweet: {tweet_data['tweet_link']}")

                        except Exception as e:
                            self.safe_log("ERROR", f"Error processing individual tweet: {str(e)}")
                            continue

                    if total_scrolls % checkpoint_frequency == 0:
                        self.save_checkpoint()

                    if not self.scroll_page() and not new_tweets_found:
                        self.safe_log("INFO", "Reached end of timeline or no new tweets found")
                        break

                    total_scrolls += 1

                except Exception as e:
                    self.safe_log("ERROR", f"Error during scrolling iteration: {str(e)}")
                    self.save_checkpoint()
                    time.sleep(10)
                    continue

        except Exception as e:
            self.safe_log("ERROR", f"Major error in tweet collection: {str(e)}")
            raise
        finally:
            self.save_checkpoint()

    def save_tweets_to_csv(self):
        try:
            if not os.path.exists('tweets'):
                os.makedirs('tweets')

            csv_path = os.path.join('tweets', f'{self.company_handle}_timeline_tweets33.csv')
            
            fieldnames = [
                "tweet_id", "tweet_link", "author_name", "author_handle", 
                "text", "timestamp", "likes", "retweets", "replies",
                "image_urls", "is_reply", "reply_to", "conversation_id"
            ]

            with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for tweet in self.tweet_data:
                    tweet = tweet.copy()
                    tweet["image_urls"] = "|".join(tweet["image_urls"]) if tweet["image_urls"] else ""
                    writer.writerow(tweet)

            self.safe_log("INFO", f"Saved {len(self.tweet_data)} tweets to {csv_path}")
        except Exception as e:
            self.safe_log("ERROR", f"Error saving to CSV: {str(e)}")
            self.save_checkpoint()

    def cleanup(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            self.safe_log("ERROR", f"Error during cleanup: {str(e)}")

    def run(self):
        try:
            self.setup_driver()
            self.collect_tweets()
            self.save_tweets_to_csv()
        except Exception as e:
            self.safe_log("ERROR", f"Error in main execution: {str(e)}")
        finally:
            self.cleanup()

def run_multiple_scrapers(accounts):
    """
    Run multiple scrapers simultaneously
    accounts: list of dicts with keys 'handle', 'start_date', 'end_date'
    """
    scrapers = []
    
    # Create and start scrapers
    for account_info in accounts:
        scraper = TwitterScraper(account_info)
        scraper.start()
        scrapers.append(scraper)
        
    try:
        # Wait for user interrupt
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Received interrupt, stopping scrapers...")
        # Stop all scrapers
        for scraper in scrapers:
            scraper.stop()
        
        # Wait for all scrapers to finish
        for scraper in scrapers:
            scraper.join()
            
    logging.info("All scrapers finished")

if __name__ == "__main__":
    # Example usage
    accounts = [
        {
            "handle": "FibeIndia",
            "start_date": "2023-10-24",
            "end_date": "2024-10-24"
        },
        {
            "handle": "casheApp",
            "start_date": "2023-10-24",
            "end_date": "2024-10-24"
        }
    ]
    
    run_multiple_scrapers(accounts)