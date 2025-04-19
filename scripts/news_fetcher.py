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

# Tüm haberlerin saklanacağı listemizi oluşturuyoruz
articles = []

# RSS beslemelerini döngü ile gezerek her bir haber için gerekli bilgileri alıyoruz
for rss_url in rss_urls:
    
    # RSS beslemesini çekiyoruz ve feedparser kullanarak RSS beslemesini parse ediyoruz
    feed = feedparser.parse(rss_url)
    
    # Her bir haber için döngüyü başlatıyoruz
    for entry in feed.entries:
        # Haber içindeki title'ı alıp temizliyoruz
        title = entry.get("title", "").strip()
        
        # Yayın tarihini alıp YYYY-MM-DD formatına çeviriyoruz
        pub_date = ""
        if "published_parsed" in entry:
            pub_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
        
        # Eğer haber içinde author bilgisi varsa onu alıyoruz, yoksa "TRT Haber" olarak sabitliyoruz
        source = entry.get("author", "TRT Haber").strip()
        
        # Haber içeriğini alıyoruz.
        text = ""
        if "content" in entry:
            text = entry.content[0].value
        elif "content:encoded" in entry:
            text = entry["content:encoded"]
        else:
            text = entry.get("summary", "")
        
        # HTML etiketlerini temizleyip sade metne dönüştürüyoruz
        soup = BeautifulSoup(text, "html.parser")
        clean_text = soup.get_text(separator="\n").strip()
        
        # Haber formatına uygun sözlük oluşturup
        article = {
            "title": title,
            "date": pub_date,
            "source": source,
            "text": clean_text
        }
        # listeye ekliyoruz
        articles.append(article)
        
save_dir = Path(NEWS_RAW_DIR).parent
save_dir.mkdir(parents=True, exist_ok=True)

with open(NEWS_RAW_DIR, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"{len(articles)} adet haber {NEWS_RAW_DIR} dosyasına kaydedildi.")
