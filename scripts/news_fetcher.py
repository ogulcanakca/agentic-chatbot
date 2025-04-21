# scripts/news_fetcher.py

import feedparser
import json
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from configs.script_config import rss_urls, NEWS_RAW_DIR

# Create a list to store all news articles
articles = []

# Iterate through each RSS feed URL and extract necessary information for each article
for rss_url in rss_urls:
    
    # Fetch and parse the RSS feed using feedparser
    feed = feedparser.parse(rss_url)
    
    # Loop through each article in the feed
    for entry in feed.entries:
        # Get and clean the title of the article
        title = entry.get("title", "").strip()
        
        # Retrieve and format the publication date as YYYY-MM-DD
        pub_date = ""
        if "published_parsed" in entry:
            pub_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
        
        # If the article has an author, get it; otherwise, default to "TRT Haber"
        source = entry.get("author", "TRT Haber").strip()
        
        # Retrieve the content of the article
        text = ""
        if "content" in entry:
            text = entry.content[0].value
        elif "content:encoded" in entry:
            text = entry["content:encoded"]
        else:
            text = entry.get("summary", "")
        
        # Clean HTML tags and convert to plain text
        soup = BeautifulSoup(text, "html.parser")
        clean_text = soup.get_text(separator="\n").strip()
        
        # Create a dictionary with the article information
        article = {
            "title": title,
            "date": pub_date,
            "source": source,
            "text": clean_text
        }
        # Add the article to the list
        articles.append(article)
        
# Create the directory if it doesn't exist
save_dir = Path(NEWS_RAW_DIR).parent
save_dir.mkdir(parents=True, exist_ok=True)

# Save all articles to a JSON file
with open(NEWS_RAW_DIR, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"{len(articles)} articles saved to {NEWS_RAW_DIR}.")
