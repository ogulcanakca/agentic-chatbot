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

from configs.script_config import base_url, search_url, ajax_url, base_headers,  current_page, all_matching_articles
from configs.script_config import max_pages_to_fetch, page_size_requested, results_count_threshold, RESMI_NEWS_RAW_DIR, RESMI_NEWS_FILE_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# HTML'den gerekli bilgileri çekmek için kullanılacak fonksiyon
def fetch_html(url, session):
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"URL alınırken hata oluştu {url}: {e}")
        return None

# Gazeteleri parse etmek için kullanılacak fonksiyon
def parse_article_page(url, session):
    html_content = fetch_html(url, session)
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}
    
    # Başlık, tarih ve içerik için gerekli seçicileri kullanarak verileri çekiyoruz
    try:
        title_tag = soup.select_one('div.detay-spot-category h1')
        if not title_tag or not title_tag.get_text(strip=True):
             title_tag = soup.select_one('h1')
        data['title'] = title_tag.get_text(strip=True) if title_tag else "Title not found"
        if data['title'] == "Title not found":
             logging.warning(f"Başlık etiketi bulunamadı {url}")

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
                logging.warning(f"Tarih dizesi '{date_str_full}' (çıkarılan '{date_part_text}') üzerinde ayrıştırma hatası: {e}")
                data['date'] = "Date not found"
        else:
             logging.warning(f"Date etiketi 'span.tarih' token ile bulunamadı {url}")
             data['date'] = "Date not found"

        # İçerik bölümünü çekiyoruz
        content_div = soup.select_one('div.detay-icerik')
        if not content_div: 
             content_div = soup.select_one('article')
        if content_div:
            paragraphs = content_div.find_all('p', recursive=True)
            text_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            data['text'] = '\n'.join(text_parts)
            if not data['text']:
                 logging.warning(f"İçerik bölümü bulundu ama paragraf metni çıkarılamadı {url}")
                 data['text'] = "Content not found or empty."
        else:
            logging.warning(f"Ana içerik div'i bulunamadı {url}'de")
            data['text'] = "Content not found"

        # Source
        data['source'] = "AA"
        # Ensure keys
        for key in ['title', 'date', 'source', 'text']:
            if key not in data:
                 data[key] = f"{key.capitalize()} not found"
        return data
    except Exception as e:
        logging.error(f"{url} sayfası ayrıştırılırken hata oluştu: {e}")
        return None

# Session nesnesi oluşturuyoruz ve başlıkları ayarlıyoruz
session = requests.Session()
session.headers.update(base_headers)

# İlk sayfayı çekerek çerezleri ve token'ı alıyoruz
logging.info(f"Çerezler ve token için ilk sayfa getiriliyor: {search_url}")
initial_html = None
try:
    initial_response = session.get(search_url, timeout=15)
    initial_response.raise_for_status()
    initial_response.encoding = initial_response.apparent_encoding
    initial_html = initial_response.text
except requests.exceptions.RequestException as e:
    logging.error(f"İlk sayfa alınırken hata oluştu: {e}")
    exit()

if not initial_html:
    logging.error("İlk arama sayfası içeriği alınamadı. Çıkılıyor.")
    exit()

# Token'ı parse ediyoruz
initial_soup = BeautifulSoup(initial_html, 'html.parser')
token_tag = initial_soup.select_one('input[name="__RequestVerificationToken"]')
if not token_tag or not token_tag.get('value'):
    logging.error("İlk HTML'de __RequestVerificationToken bulunamadı. Çıkılıyor.")
    exit()
anti_forgery_token = token_tag['value']
logging.info(f"Anti-forgery token bulundu: {anti_forgery_token[:10]}...")

# AJAX URL'sini ayarlıyoruz. Çerezleri ve token'ı kullanarak POST isteği yapacağız.
while current_page <= max_pages_to_fetch:
    logging.info(f"--- Fetching Page {current_page} ---")

    # Mevcut sayfa için AJAX payload'ını oluşturuyoruz
    payload = {
        'PageSize': page_size_requested,
        'Keywords': "Resmi Gazete",
        'CategoryId': "",
        'TypeId': 1,
        'Page': current_page,
        '__RequestVerificationToken': anti_forgery_token
    }

    # AJAX POST isteği için header'ları hazırlıyoruz
    ajax_headers = {
        'Referer': search_url,
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': base_url,
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }
    current_headers = session.headers.copy()
    current_headers.update(ajax_headers)

    logging.info(f"Sayfa {current_page} için AJAX POST isteği yapılıyor: {ajax_url}")
    
    # POST isteğini yapıyoruz
    search_results = None
    documents_on_this_page = []
    try:
        ajax_response = session.post(ajax_url, headers=current_headers, data=payload, timeout=25)
        ajax_response.raise_for_status()
        search_results = ajax_response.json()
        logging.info(f"AJAX isteği Sayfa {current_page} için başarılı.")

        # Cevapta 'Documents' var mı ve liste mi kontrol ediyoruz
        if search_results and 'Documents' in search_results and isinstance(search_results['Documents'], list):
             documents_on_this_page = search_results['Documents']
             logging.info(f"Sayfa {current_page} için {len(documents_on_this_page)} document maddesi bulundu.")
        else:
             logging.warning(f"Sayfa {current_page} için yanıtta 'Documents' listesi bulunamadı veya geçersiz biçim. Sayfalandırma durduruluyor.")
             break

    # AJAX isteği sırasında hata olursa veya JSON parse edilemezse hata mesajı veriyoruz
    except requests.exceptions.RequestException as e:
        logging.error(f"Sayfa {current_page} için AJAX POST isteği sırasında hata oluştu: {e}")
        break 
    except json.JSONDecodeError as e:
        logging.error(f"Sayfa {current_page} için JSON yanıtı ayrıştırılırken hata oluştu: {e}")
        if 'ajax_response' in locals(): logging.error(f"Response Text: {ajax_response.text[:500]}...")
        break 
    
    # Eğer bu sayfada hiç doküman dönmediyse, döngüyü bitiriyoruz
    if not documents_on_this_page:
        logging.info(f"Sayfa {current_page} için hiç haber dönmedi. Sayfalama durduruluyor.")
        break

    # Bu sayfadaki dokümanları işliyoruz
    page_processed_count = 0
    for item in documents_on_this_page:
        title_text = item.get('Title')
        route = item.get('Route')

        # Filtreleyeip eşleşenleri buluyoruz
        # Eğer başlık ve route varsa ve başlıkta "Resmi Gazete'de" geçiyorsa, haberi parse ediyoruz
        if title_text and route and "Resmi Gazete'de" in title_text:
            article_url = base_url + route
            logging.info(f"Bulunan eşleşen haber: '{title_text}'. URL: {article_url}")

            # Haber sayfasını parse edip
            article_data = parse_article_page(article_url, session)
            # Eğer haber verisi varsa, listeye ekliyoruz
            if article_data:
                all_matching_articles.append(article_data)
                logging.info(f"Başarıyla ayrıştırıldı: {article_url}")
                page_processed_count += 1
            else:
                logging.warning(f"Haber sayfası ayrıştırılamadı: {article_url}")
            time.sleep(0.5)

    logging.info(f"Sayfa {current_page} için işlenen eşleşen haber sayısı: {page_processed_count}.")

    # Sayfalama durma koşulunu kontrol ediyoruz
    # Eğer dönen doküman sayısı istediğimiz sayfa boyutundan az ise, son sayfadır.
    if len(documents_on_this_page) < results_count_threshold:
         logging.info(f"Dönen doküman sayısı ({len(documents_on_this_page)}) eşik değerinden ({results_count_threshold}) az. Sayfalama durduruluyor.")
         break

    current_page += 1
    time.sleep(1) 
    
logging.info(f"Sayfalama döngüsü tamamlandı. Toplam bulunan eşleşen haber sayısı: {len(all_matching_articles)}")

output_json = json.dumps(all_matching_articles, indent=4, ensure_ascii=False)
print(output_json)

save_dir = Path(RESMI_NEWS_RAW_DIR).parent
save_dir.mkdir(parents=True, exist_ok=True)

try:
    with open(RESMI_NEWS_RAW_DIR, "w", encoding="utf-8") as f:
        f.write(output_json)
    logging.info(f"Sonuçlar {RESMI_NEWS_FILE_NAME} dosyasına kaydedildi.")
except IOError as e:
    logging.error(f"Sonuçları dosyaya yazarken hata oluştu: {e}")