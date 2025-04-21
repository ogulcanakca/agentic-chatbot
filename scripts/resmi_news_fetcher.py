# scripts/resmi_news_fetcher.py

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
import logging
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from configs.script_config import base_url, search_url, ajax_url, base_headers, current_page, all_matching_articles
from configs.script_config import max_pages_to_fetch, page_size_requested, results_count_threshold, RESMI_NEWS_RAW_DIR, RESMI_NEWS_FILE_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to fetch HTML and extract necessary information
def fetch_html(url, session):
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None

# Function to parse article pages
def parse_article_page(url, session):
    html_content = fetch_html(url, session)
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}

    # Extract title, date, and content using selectors
    try:
        title_tag = soup.select_one('div.detay-spot-category h1')
        if not title_tag or not title_tag.get_text(strip=True):
            title_tag = soup.select_one('h1')
        data['title'] = title_tag.get_text(strip=True) if title_tag else "Title not found"
        if data['title'] == "Title not found":
            logging.warning(f"Title tag not found at {url}")

        date_tag = soup.select_one('span.tarih')
        if date_tag:
            date_str_full = date_tag.get_text(strip=True)
            date_part_text = ""
            try:
                if date_str_full:
                    date_part_text = date_str_full.split('-')[0].strip()
                    date_obj = datetime.strptime(date_part_text, '%d.%m.%Y')
                    data['date'] = date_obj.strftime('%Y-%m-%d')
                else:
                    raise ValueError("Date string is empty")
            except (ValueError, IndexError, TypeError) as e:
                logging.warning(f"Failed to parse date string '{date_str_full}' (extracted '{date_part_text}'): {e}")
                data['date'] = "Date not found"
        else:
            logging.warning(f"Date tag 'span.tarih' not found at {url}")
            data['date'] = "Date not found"

        # Extract content section
        content_div = soup.select_one('div.detay-icerik')
        if not content_div:
            content_div = soup.select_one('article')
        if content_div:
            paragraphs = content_div.find_all('p', recursive=True)
            text_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            data['text'] = '\n'.join(text_parts)
            if not data['text']:
                logging.warning(f"Content section found but no paragraph text extracted at {url}")
                data['text'] = "Content not found or empty."
        else:
            logging.warning(f"Main content div not found at {url}")
            data['text'] = "Content not found"

        # Source
        data['source'] = "AA"
        # Ensure all keys exist
        for key in ['title', 'date', 'source', 'text']:
            if key not in data:
                data[key] = f"{key.capitalize()} not found"
        return data
    except Exception as e:
        logging.error(f"Error parsing page {url}: {e}")
        return None

# Create a session object and set headers
session = requests.Session()
session.headers.update(base_headers)

# Fetch the first page to obtain cookies and token
logging.info(f"Fetching initial page for cookies and token: {search_url}")
initial_html = None
try:
    initial_response = session.get(search_url, timeout=15)
    initial_response.raise_for_status()
    initial_response.encoding = initial_response.apparent_encoding
    initial_html = initial_response.text
except requests.exceptions.RequestException as e:
    logging.error(f"Error fetching initial page: {e}")
    exit()

if not initial_html:
    logging.error("Initial search page content could not be retrieved. Exiting.")
    exit()

# Parse the token
initial_soup = BeautifulSoup(initial_html, 'html.parser')
token_tag = initial_soup.select_one('input[name="__RequestVerificationToken"]')
if not token_tag or not token_tag.get('value'):
    logging.error("Request verification token '__RequestVerificationToken' not found in initial HTML. Exiting.")
    exit()
anti_forgery_token = token_tag['value']
logging.info(f"Found anti-forgery token: {anti_forgery_token[:10]}...")

# Loop through pages using AJAX requests
while current_page <= max_pages_to_fetch:
    logging.info(f"--- Fetching Page {current_page} ---")

    # Prepare AJAX payload for the current page
    payload = {
        'PageSize': page_size_requested,
        'Keywords': "Resmi Gazete",
        'CategoryId': "",
        'TypeId': 1,
        'Page': current_page,
        '__RequestVerificationToken': anti_forgery_token
    }

    # Prepare headers for AJAX POST request
    ajax_headers = {
        'Referer': search_url,
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': base_url,
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }
    current_headers = session.headers.copy()
    current_headers.update(ajax_headers)

    logging.info(f"Sending AJAX POST request for page {current_page}: {ajax_url}")
    
    # Make the POST request
    search_results = None
    documents_on_this_page = []
    try:
        ajax_response = session.post(ajax_url, headers=current_headers, data=payload, timeout=25)
        ajax_response.raise_for_status()
        search_results = ajax_response.json()
        logging.info(f"AJAX request successful for page {current_page}.")

        # Check if 'Documents' exists and is a list
        if search_results and 'Documents' in search_results and isinstance(search_results['Documents'], list):
            documents_on_this_page = search_results['Documents']
            logging.info(f"Found {len(documents_on_this_page)} document items on page {current_page}.")
        else:
            logging.warning(f"'Documents' list not found or invalid in response for page {current_page}. Stopping pagination.")
            break

    except requests.exceptions.RequestException as e:
        logging.error(f"Error during AJAX POST request for page {current_page}: {e}")
        break
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON response for page {current_page}: {e}")
        if 'ajax_response' in locals():
            logging.error(f"Response Text: {ajax_response.text[:500]}...")
        break
    
    # If no documents returned, end loop
    if not documents_on_this_page:
        logging.info(f"No articles returned for page {current_page}. Stopping pagination.")
        break

    # Process documents on current page
    page_processed_count = 0
    for item in documents_on_this_page:
        title_text = item.get('Title')
        route = item.get('Route')

        # Filter and match articles
        if title_text and route and "Resmi Gazete'de" in title_text:
            article_url = base_url + route
            logging.info(f"Matched article found: '{title_text}'. URL: {article_url}")

            # Parse the article page
            article_data = parse_article_page(article_url, session)
            if article_data:
                all_matching_articles.append(article_data)
                logging.info(f"Successfully parsed: {article_url}")
                page_processed_count += 1
            else:
                logging.warning(f"Failed to parse article page: {article_url}")
            time.sleep(0.5)

    logging.info(f"Number of matched articles processed on page {current_page}: {page_processed_count}.")

    # Check pagination stop condition
    if len(documents_on_this_page) < results_count_threshold:
        logging.info(f"Number of returned documents ({len(documents_on_this_page)}) is less than threshold ({results_count_threshold}). Stopping pagination.")
        break

    current_page += 1
    time.sleep(1)

logging.info(f"Pagination loop completed. Total matched articles found: {len(all_matching_articles)}")

output_json = json.dumps(all_matching_articles, indent=4, ensure_ascii=False)
print(output_json)

save_dir = Path(RESMI_NEWS_RAW_DIR).parent
save_dir.mkdir(parents=True, exist_ok=True)

try:
    with open(RESMI_NEWS_RAW_DIR, "w", encoding="utf-8") as f:
        f.write(output_json)
    logging.info(f"Results saved to {RESMI_NEWS_FILE_NAME}.")
except IOError as e:
    logging.error(f"Error writing results to file: {e}")
