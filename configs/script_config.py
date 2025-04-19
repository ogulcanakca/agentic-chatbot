# configs/script_config.py

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# İşlenmiş veri dosyalarının saklandığı dizin
PROCESSED_DATA_DIR = project_root / "data" / "processed"

# scripts/generate_embeddings.py için config

# Veri kaynaklarımızın bulunduğu klasör isimleri
DATA_FOLDERS = ["resmi_gazete", "haberler"]

# Ham veri dosyalarının saklandığı dizin
RAW_DATA_DIR = project_root / "data" / "raw"

# Batch'ler haline işlem yapıyoruz RAM kullanımını kontrol altında tutmak için
PROCESSING_BATCH_SIZE = 128

# scripts/process_data.py için config

# Veri kaynaklarının dosya isimleri
DATA_SOURCES = {
    DATA_FOLDERS[0]: "aa_resmi_gazete_tum_haberler.json",
    DATA_FOLDERS[1]: "trt_haberler.json"
}

# Chunking parametreleri
CHUNK_SIZE = 1000 
CHUNK_OVERLAP = 150

# scripts/news_fetcher.py için config

# RSS beslemelerinin URL'leri
rss_urls = [
    "https://www.trthaber.com/saglik_articles.rss",
    "https://www.trthaber.com/infografik_articles.rss",
    "https://www.trthaber.com/spor_articles.rss"
]

NEWS_RAW_DATA_DIR = RAW_DATA_DIR / DATA_FOLDERS[1]
NEWS_RAW_DIR = NEWS_RAW_DATA_DIR / "trt_haberler.json"

# scripts/resmi_news_fetcher.py için config

# Resmi Gazete içeriklerinin çekildiği URL'ler
base_url = "https://www.aa.com.tr"
search_url = "https://www.aa.com.tr/tr/search/?s=Resmi+Gazete&tag=1"
ajax_url = "https://www.aa.com.tr/tr/Search/Search"

# Web scraping işlemi için HTTP isteklerinde kullanılacak User-Agent başlığımız
base_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

current_page = 1
all_matching_articles = [] # Tüm sayfalardan bulunan eşleşen makaleler
page_size_requested = 100  # AJAX isteğinde gönderdiğimiz sayfa boyutu
max_pages_to_fetch = 10    # Güvenlik için maksimum sayfa limiti
results_count_threshold = 20 # Sitenin JS'sindeki durma kontrolü

# Resmi Gazete haberlerinin RAW halinin saklanacağı dosya ismi
RESMI_NEWS_FILE_NAME = DATA_SOURCES[DATA_FOLDERS[0]]
# Resmi Gazete haberlerinin ham verilerinin saklanacağı dizin
RESMI_NEWS_RAW_DATA_DIR = RAW_DATA_DIR / DATA_FOLDERS[0]
# Resmi Gazete haberlerinin ham verilerinin saklanacağı dosya yolu
RESMI_NEWS_RAW_DIR = RESMI_NEWS_RAW_DATA_DIR / RESMI_NEWS_FILE_NAME


