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

# Set up logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

class TwitterScraper:
    def __init__(self):
        self.account_url = "https://x.com/FibeIndia/with_replies"
        self.start_date = "2024-08-01"
        self.end_date = "2024-10-24"
        self.company_handle = "FibeIndia"
        self.tweet_data = []
        self.checkpoint_file = "fibe_india_tweet_checkpoint2.json"
        self.processed_tweets = set()  # Track processed tweet IDs
        self.setup_driver()
        self.setup_signal_handlers()

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

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        logging.info("Received shutdown signal. Saving checkpoint and cleaning up...")
        self.save_checkpoint()
        self.cleanup()
        sys.exit(0)

    def load_checkpoint(self):
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    self.tweet_data = checkpoint_data['tweet_data']
                    self.processed_tweets = set(checkpoint_data['processed_tweets'])
                logging.info(f"Loaded {len(self.tweet_data)} tweets from checkpoint")
                return True
        except Exception as e:
            logging.error(f"Error loading checkpoint: {str(e)}")
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
            logging.info(f"Saved checkpoint with {len(self.tweet_data)} tweets")
        except Exception as e:
            logging.error(f"Error saving checkpoint: {str(e)}")

    def extract_tweet_id(self, tweet_link):
        """Extract tweet ID from tweet link"""
        try:
            return tweet_link.split('/')[-1]
        except Exception:
            return None

    def extract_count_by_testid(self, tweet, testid):
        """Extract engagement metrics from tweet"""
        try:
            button = tweet.find('button', {'data-testid': testid})
            if button:
                span = button.find('span', class_='css-1jxf684')
                if span:
                    count_text = span.get_text().strip()
                    # Handle K (thousands) and M (millions) suffixes
                    if 'K' in count_text:
                        return int(float(count_text.replace('K', '')) * 1000)
                    elif 'M' in count_text:
                        return int(float(count_text.replace('M', '')) * 1000000)
                    elif count_text.isdigit():
                        return int(count_text)
        except Exception as e:
            logging.error(f"Error extracting {testid} count: {str(e)}")
        return 0

    def extract_tweet_data(self, tweet):
        """Extract all data from a tweet element"""
        try:
            tweet_data = {
                "tweet_link": None,
                "tweet_id": None,
                "author_name": None,
                "author_handle": None,
                "text": None,
                "timestamp": None,
                "likes": 0,
                "retweets": 0,
                "replies": 0,
                "image_urls": [],
                "is_reply": False,
                "reply_to": None,
                "conversation_id": None
            }

            # Extract tweet link and ID
            link_element = tweet.find("a", href=lambda href: href and "/status/" in href)
            if link_element:
                tweet_data["tweet_link"] = "https://x.com" + link_element['href']
                tweet_data["tweet_id"] = self.extract_tweet_id(tweet_data["tweet_link"])

            # Extract author information
            author_element = tweet.find("div", {"data-testid": "User-Name"})
            if author_element:
                # Extract author name
                name_spans = author_element.find_all("span", recursive=True)
                for span in name_spans:
                    text = span.get_text().strip()
                    if text and not text.startswith("@"):
                        tweet_data["author_name"] = text
                        break

                # Extract author handle
                handle_span = author_element.find("span", string=lambda text: text and text.startswith("@"))
                if handle_span:
                    tweet_data["author_handle"] = handle_span.text.strip()

            # Extract tweet text
            text_element = tweet.find("div", {"data-testid": "tweetText"})
            if text_element:
                tweet_data["text"] = text_element.get_text(separator=' ').strip()

            # Extract timestamp
            time_element = tweet.find("time")
            if time_element:
                tweet_data["timestamp"] = time_element.get("datetime")

            # Extract engagement metrics
            tweet_data["likes"] = self.extract_count_by_testid(tweet, "like")
            tweet_data["retweets"] = self.extract_count_by_testid(tweet, "retweet")
            tweet_data["replies"] = self.extract_count_by_testid(tweet, "reply")

            # Extract images
            images = tweet.find_all("img", {"alt": "Image"})
            tweet_data["image_urls"] = [img.get("src") for img in images if img.get("src")]

            # Check if it's a reply
            reply_element = tweet.find("div", string=lambda text: text and "Replying to" in str(text))
            if reply_element:
                tweet_data["is_reply"] = True
                reply_to_element = reply_element.find("a")
                if reply_to_element:
                    tweet_data["reply_to"] = reply_to_element.get_text().strip()

            return tweet_data

        except Exception as e:
            logging.error(f"Error extracting tweet data: {str(e)}")
            return None

    def is_within_date_range(self, tweet_date):
        try:
            tweet_date_obj = datetime.strptime(tweet_date.split('T')[0], "%Y-%m-%d")
            start_date_obj = datetime.strptime(self.start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d")
            return start_date_obj <= tweet_date_obj <= end_date_obj
        except Exception as e:
            logging.error(f"Error parsing date {tweet_date}: {str(e)}")
            return False

    
    def scroll_page(self):
        try:
            last_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            
            # Scroll in smaller increments
            for _ in range(8):  # Adjust number of scrolls as needed
                self.driver.execute_script("window.scrollBy(0, window.innerHeight / 4);")
                time.sleep(0.5)  # 2 second pause between each scroll
            
            # Check if we reached new content
            new_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            return new_height != last_height
            
        except Exception as e:
            logging.error(f"Error scrolling page: {str(e)}")

    def collect_tweets(self):
        """Collect tweets directly from timeline"""
        total_scrolls = 0
        max_scrolls = 2500
        checkpoint_frequency = 20
        
        try:
            self.driver.get(self.account_url)
            logging.info("Waiting for manual login...")
            time.sleep(120)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
            )
            
            # Load existing progress
            self.load_checkpoint()
            
            while total_scrolls < max_scrolls:
                try:
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    tweets = soup.find_all("article", {"data-testid": "tweet"})
                    
                    new_tweets_found = False
                    for tweet in tweets:
                        try:
                            time_element = tweet.find("time")
                            if not time_element:
                                continue
                                
                            tweet_date = time_element.get("datetime")
                            if not self.is_within_date_range(tweet_date):
                                continue

                            # Extract tweet data
                            tweet_data = self.extract_tweet_data(tweet)
                            if not tweet_data or not tweet_data["tweet_id"]:
                                continue

                            # Skip if already processed
                            if tweet_data["tweet_id"] in self.processed_tweets:
                                continue

                            # Skip company tweets
                            if tweet_data["author_handle"] == f"@{self.company_handle}":
                                continue

                            # Add to dataset
                            self.tweet_data.append(tweet_data)
                            self.processed_tweets.add(tweet_data["tweet_id"])
                            new_tweets_found = True
                            
                            logging.info(f"Added new tweet: {tweet_data['tweet_link']}")

                        except Exception as e:
                            logging.error(f"Error processing individual tweet: {str(e)}")
                            continue

                    if total_scrolls % checkpoint_frequency == 0:
                        self.save_checkpoint()
                        logging.info(f"Checkpoint saved. Total tweets: {len(self.tweet_data)}")

                    # Scroll and check if we've reached the end
                    if not self.scroll_page() and not new_tweets_found:
                        logging.info("Reached end of timeline or no new tweets found")
                        break

                    total_scrolls += 1

                except Exception as e:
                    logging.error(f"Error during scrolling iteration: {str(e)}")
                    self.save_checkpoint()
                    time.sleep(10)
                    continue

        except Exception as e:
            logging.error(f"Major error in tweet collection: {str(e)}")
            raise
        finally:
            self.save_checkpoint()

        return self.tweet_data

    def save_tweets_to_csv(self, filename):
        """Save tweets to CSV with all fields"""
        try:
            if not os.path.exists('tweets'):
                os.makedirs('tweets')

            csv_path = os.path.join('tweets', filename)
            
            fieldnames = [
                "tweet_id", "tweet_link", "author_name", "author_handle", 
                "text", "timestamp", "likes", "retweets", "replies",
                "image_urls", "is_reply", "reply_to", "conversation_id"
            ]

            with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for tweet in self.tweet_data:
                    # Convert image_urls list to string for CSV
                    tweet = tweet.copy()
                    tweet["image_urls"] = "|".join(tweet["image_urls"]) if tweet["image_urls"] else ""
                    writer.writerow(tweet)

            logging.info(f"Saved {len(self.tweet_data)} tweets to {csv_path}")
        except Exception as e:
            logging.error(f"Error saving to CSV: {str(e)}")
            self.save_checkpoint()

    def cleanup(self):
        try:
            self.driver.quit()
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

    def run(self):
        try:
            self.collect_tweets()
            self.save_tweets_to_csv("fibe_india_timeline_tweets3.csv")
        except Exception as e:
            logging.error(f"Error in main execution: {str(e)}")
        finally:
            self.cleanup()

if __name__ == "__main__":
    scraper = TwitterScraper()
    scraper.run()