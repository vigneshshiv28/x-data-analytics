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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TwitterScraper:
    def __init__(self):
        self.account_url = "https://x.com/FibeIndia/with_replies"
        self.start_date = "2024-10-05"
        self.end_date = "2024-10-19"
        self.company_handle = "FibeIndia"
        self.customer_tweet_links = set()
        self.checkpoint_file = "checkpoint.json"
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
        """Set up handlers for graceful shutdown on SIGINT and SIGTERM"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals by saving checkpoint and closing driver"""
        logging.info("Received shutdown signal. Saving checkpoint and cleaning up...")
        self.save_checkpoint()
        self.cleanup()
        sys.exit(0)

    def load_checkpoint(self):
        """Load previously collected tweets from checkpoint file"""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint_data = json.load(f)
                    self.customer_tweet_links = set(checkpoint_data['tweet_links'])
                logging.info(f"Loaded {len(self.customer_tweet_links)} tweets from checkpoint")
                return True
        except Exception as e:
            logging.error(f"Error loading checkpoint: {str(e)}")
        return False

    def save_checkpoint(self):
        """Save current progress to checkpoint file"""
        try:
            checkpoint_data = {
                'tweet_links': list(self.customer_tweet_links),
                'timestamp': datetime.now().isoformat()
            }
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f)
            logging.info(f"Saved checkpoint with {len(self.customer_tweet_links)} tweets")
        except Exception as e:
            logging.error(f"Error saving checkpoint: {str(e)}")

    def is_within_date_range(self, tweet_date):
        try:
            tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
            start_date_obj = datetime.strptime(self.start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d")
            return start_date_obj <= tweet_date_obj <= end_date_obj
        except Exception as e:
            logging.error(f"Error parsing date {tweet_date}: {str(e)}")
            return False

    def scroll_page(self):
        """Scroll the page and handle potential errors"""
        try:
            self.driver.execute_script("window.scrollBy(0, window.innerHeight)/4;")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Error scrolling page: {str(e)}")

    def collect_customer_tweets(self):
        """Collect customer tweets with periodic checkpoints"""
        total_scrolls = 0
        max_scrolls = 5000
        checkpoint_frequency = 50  # Save checkpoint every 50 scrolls
        
        try:
            self.driver.get(self.account_url)
            logging.info("Waiting for manual login...")
            time.sleep(120)  # Allow for manual login
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
            )
            
            # Load existing progress if available
            self.load_checkpoint()
            
            while total_scrolls < max_scrolls:
                try:
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    tweets = soup.find_all("article", {"data-testid": "tweet"})
                    
                    for tweet in tweets:
                        try:
                            time_element = tweet.find("time")
                            if time_element:
                                tweet_date = time_element.get("datetime").split("T")[0]
                                
                                if self.is_within_date_range(tweet_date):
                                    author_handle_element = tweet.find(
                                        "a", 
                                        href=lambda href: href and "/status/" in href
                                    )
                                    
                                    if (author_handle_element and 
                                        self.company_handle not in author_handle_element.get('href')):
                                        tweet_link = "https://x.com" + author_handle_element['href']
                                        if tweet_link not in self.customer_tweet_links:
                                            self.customer_tweet_links.add(tweet_link)
                                            logging.info(f"Added new tweet: {tweet_link}")
                        
                        except Exception as e:
                            logging.error(f"Error processing tweet: {str(e)}")
                            continue
                    
                    self.scroll_page()
                    total_scrolls += 1
                    
                    # Save checkpoint periodically
                    if total_scrolls % checkpoint_frequency == 0:
                        self.save_checkpoint()
                        logging.info(
                            f"Checkpoint saved at scroll {total_scrolls}. "
                            f"Collected {len(self.customer_tweet_links)} tweets so far."
                        )
                
                except Exception as e:
                    logging.error(f"Error during scrolling iteration: {str(e)}")
                    self.save_checkpoint()
                    time.sleep(10)  # Wait before retrying
                    continue
                
        except Exception as e:
            logging.error(f"Major error in tweet collection: {str(e)}")
            self.save_checkpoint()
            raise
        
        finally:
            # Save final checkpoint before returning
            self.save_checkpoint()
        
        return list(self.customer_tweet_links)

    def save_tweet_links_to_csv(self, tweet_links, filename):
        """Save the tweet links to a CSV file with error handling"""
        try:
            if not os.path.exists('tweets'):
                os.makedirs('tweets')

            csv_path = os.path.join('tweets', filename)

            with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["tweet_link"])
                for tweet_link in tweet_links:
                    writer.writerow([tweet_link])

            logging.info(f"Saved tweet links to {csv_path}")
        except Exception as e:
            logging.error(f"Error saving to CSV: {str(e)}")
            # Try to save to a backup file
            self.save_checkpoint()

    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

    def run(self):
        """Main execution method"""
        try:
            customer_tweets = self.collect_customer_tweets()
            self.save_tweet_links_to_csv(customer_tweets, "fibe_india_tweet_links2.csv")
        except Exception as e:
            logging.error(f"Error in main execution: {str(e)}")
        finally:
            self.cleanup()

if __name__ == "__main__":
    scraper = TwitterScraper()
    scraper.run()