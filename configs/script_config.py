# configs/script_config.py

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Directory where processed data files are stored
PROCESSED_DATA_DIR = project_root / "data" / "processed"

# Config for scripts/generate_embeddings.py

# Names of folders containing our data sources
DATA_FOLDERS = ["resmi_gazete", "haberler"]

# Directory where raw data files are stored
RAW_DATA_DIR = project_root / "data" / "raw"

# We process data in batches to keep RAM usage under control
PROCESSING_BATCH_SIZE = 128

# Config for scripts/process_data.py

# Filenames of data sources
DATA_SOURCES = {
    DATA_FOLDERS[0]: "aa_resmi_gazete_tum_haberler.json",
    DATA_FOLDERS[1]: "trt_haberler.json"
}

# Chunking parameters
CHUNK_SIZE = 1000 
CHUNK_OVERLAP = 150

# Config for scripts/news_fetcher.py

# RSS feed URLs
rss_urls = [
    "https://www.trthaber.com/saglik_articles.rss",
    "https://www.trthaber.com/infografik_articles.rss",
    "https://www.trthaber.com/spor_articles.rss"
]

NEWS_RAW_DATA_DIR = RAW_DATA_DIR / DATA_FOLDERS[1]
NEWS_RAW_DIR = NEWS_RAW_DATA_DIR / "trt_haberler.json"

# Config for scripts/resmi_news_fetcher.py

# URLs for fetching Official Gazette content
base_url = "https://www.aa.com.tr"
search_url = "https://www.aa.com.tr/tr/search/?s=Resmi+Gazete&tag=1"
ajax_url = "https://www.aa.com.tr/tr/Search/Search"

# User-Agent header to be used in HTTP requests for web scraping
base_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

current_page = 1
all_matching_articles = []  # All matching articles found from pages
page_size_requested = 100   # Page size sent in AJAX request
max_pages_to_fetch = 10     # Safety limit for maximum number of pages to fetch
results_count_threshold = 20  # Stop condition used in site's JavaScript

# File name for storing raw Official Gazette news
RESMI_NEWS_FILE_NAME = DATA_SOURCES[DATA_FOLDERS[0]]
# Directory for storing raw Official Gazette data
RESMI_NEWS_RAW_DATA_DIR = RAW_DATA_DIR / DATA_FOLDERS[0]
# File path for storing raw Official Gazette news
RESMI_NEWS_RAW_DIR = RESMI_NEWS_RAW_DATA_DIR / RESMI_NEWS_FILE_NAME
