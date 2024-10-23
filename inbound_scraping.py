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
    try:
        tweet_date_obj = datetime.strptime(tweet_date, "%Y-%m-%d")
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        logging.info(f"Checking tweet date {tweet_date} within range {start_date} to {end_date}")
        
        return start_date_obj <= tweet_date_obj <= end_date_obj
    except Exception as e:
        logging.error(f"Error parsing date {tweet_date}: {str(e)}")
        return False

def scroll_page():
    driver.execute_script("window.scrollBy(0, window.innerHeight)/4;")
    time.sleep(5)

def collect_customer_tweets():
    customer_tweet_links = set()
    total_scrolls = 0
    max_scrolls = 1000
    
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
                    
                    #if tweet_date < start_date:
                        #logging.info(f"Reached tweets before start date. Collected {len(customer_tweet_links)} tweets.")
                        #return list(customer_tweet_links)

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

def verify_and_save_tweet_links(tweet_url):
    """Only navigate to the tweet link and verify if it loads properly."""
    driver.get(tweet_url)
    logging.info(f"Visiting tweet link: {tweet_url}")
    
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
        )
        return tweet_url

    except Exception as e:
        logging.error(f"Error loading tweet {tweet_url}: {str(e)}")
        return None

def save_tweet_links_to_csv(tweet_links, filename):
    """Save the tweet links to a CSV file."""
    if not os.path.exists('tweets'):
        os.makedirs('tweets')

    csv_path = os.path.join('tweets', filename)

    # Write to CSV
    with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["tweet_link"])

        for tweet_link in tweet_links:
            writer.writerow([tweet_link])

    logging.info(f"Saved tweet links to {csv_path}")

# Main execution
customer_tweets = collect_customer_tweets()
#valid_tweet_links = []

#for i, tweet_url in enumerate(customer_tweets, 1):
#    logging.info(f"Processing tweet {i} of {len(customer_tweets)}")
    
#    valid_link = verify_and_save_tweet_links(tweet_url)
#    if valid_link:
#        valid_tweet_links.append(valid_link)

# Save all valid tweet links to a CSV file
save_tweet_links_to_csv(cutomer_tweets, "fibe_India_tweet_links1.csv")

logging.info("All tweet links have been saved to the CSV file.")
driver.quit()
