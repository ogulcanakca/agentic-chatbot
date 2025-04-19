# app/tools/external_apis.py

import wikipedia
import logging
from pathlib import Path
from typing import Optional
import time
from tavily import TavilyClient
from langchain.tools import Tool
import sys
from pathlib import Path
import os # os modülünü import et
from langchain_community.tools import DuckDuckGoSearchRun

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# api_config'i import etmek load_env()'in çalışmasını tetikler
try:
    from configs import api_config 
except ImportError:
    logging.error("configs.api_config modülü yüklenemedi!")

# TAVILY_API_KEY'i os.getenv ile al
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- Kalan kod aynı ---

# Tavily client ve hata mesajını saklayacağımız değişkenler
tavily_client: Optional[TavilyClient] = None 
tavily_error_message: Optional[str] = None

# Eğer TAVILY_API_KEY ayarlıysa Tavily API istemcisini başlat
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        logging.info("Tavily API client başarıyla başlatıldı.")
    except Exception as e:
        tavily_error_message = f"Tavily API client başlatılırken hata: {e}."
        logging.error(tavily_error_message, exc_info=True)
        tavily_client = None
else:
    # API Key yoksa logla
    logging.warning("Ortam değişkeni 'TAVILY_API_KEY' bulunamadı veya boş. Tavily client başlatılamadı.")
    tavily_error_message = "Tavily API anahtarı ayarlanmamış."


# Wikipedia arama fonksiyonu (değişiklik yok)
def search_wikipedia(query: str, lang: str = "tr", sentences: int = 5) -> str:
    # ... (fonksiyon içeriği aynı) ...
    logging.info(f"Wikipedia'da '{query}' aranıyor (dil={lang})...")
    wikipedia.set_lang(lang)
    try:
        page = wikipedia.page(query, auto_suggest=False)
        summary = wikipedia.summary(query, sentences=sentences, auto_suggest=False)
        logging.info(f"Wikipedia özeti bulundu (Sayfa: {page.title}, URL: {page.url}).")
        return f"Wikipedia Sonucu ({page.title}):\n{summary}\n\nKaynak: {page.url}"
    except wikipedia.exceptions.PageError:
        logging.warning(f"Wikipedia'da '{query}' sayfası bulunamadı.")
        return f"Üzgünüm, Wikipedia'da '{query}' hakkında bir sayfa bulamadım."
    except wikipedia.exceptions.DisambiguationError as e:
        options_preview = ", ".join(e.options[:5])
        logging.warning(f"Wikipedia sorgusu '{query}' birden fazla anlama geliyor: {options_preview}...")
        return f"'{query}' sorgusu birden fazla anlama geliyor (Örn: {options_preview}...). Lütfen sorgunuzu netleştirin."
    except Exception as e:
        logging.error(f"Wikipedia araması sırasında beklenmedik bir hata oluştu: {e}", exc_info=True)
        return f"Wikipedia araması sırasında bir sorun oluştu: {e}"

# Wikipedia tool tanımı (değişiklik yok)
wikipedia_tool = Tool(
    name="WikipediaSearch",
    func=search_wikipedia,
    description="Belirli bir konu, kişi, yer veya olay hakkında ansiklopedik bilgi almak için kullanılır. Tanımlar ve genel bilgiler için iyidir. Türkçe arama yapar."
)

# Tavily arama fonksiyonu (değişiklik yok)
def search_web_tavily(query: str, max_results: int = 5) -> str:
    if not tavily_client:
        return tavily_error_message or "Tavily API istemcisi kullanılamıyor."
    # ... (fonksiyon içeriği aynı) ...
    logging.info(f"Tavily ile web'de '{query}' aranıyor (max_results={max_results})...")
    try: # API çağrısını try-except içine almak iyi bir pratik
        response = tavily_client.search(query=query, search_depth="basic", max_results=max_results)
        results = response.get('results', [])
        if results:
            formatted_results = []
            for res in results:
                formatted_results.append(
                    f"Başlık: {res.get('title', 'N/A')}\n"
                    f"URL: {res.get('url', 'N/A')}\n"
                    f"Özet: {res.get('content', 'N/A')}"
                )
            logging.info(f"Tavily {len(results)} sonuç buldu.")
            return "\n\n---\n\n".join(formatted_results)
        else:
            logging.warning("Tavily araması sonuç döndürmedi.")
            return "Web araması (Tavily) bu sorgu için sonuç bulamadı."
    except Exception as e:
        logging.error(f"Tavily API çağrısı sırasında hata: {e}", exc_info=True)
        return f"Web araması (Tavily) sırasında bir sorun oluştu: {e}"


# DuckDuckGo arama fonksiyonu (değişiklik yok)
def search_web_duckduckgo(query: str) -> str:
    # ... (fonksiyon içeriği aynı) ...
    logging.info(f"DuckDuckGo ile web'de '{query}' aranıyor...")
    try:
        ddg_search = DuckDuckGoSearchRun()
        results = ddg_search.run(query)
        if results and "No good DuckDuckGo Search Result" not in results:
            logging.info("DuckDuckGo araması sonuç döndürdü.")
            return results
        else:
            logging.warning("DuckDuckGo araması anlamlı bir sonuç döndürmedi.")
            return "Web araması (DuckDuckGo) bu sorgu için sonuç bulamadı."
    except Exception as e:
        logging.error(f"DuckDuckGo web araması sırasında hata: {e}", exc_info=True)
        return f"Web araması (DuckDuckGo) sırasında bir sorun oluştu: {e}"

# Birleşik web arama fonksiyonu (değişiklik yok)
def search_web(query: str) -> str:
    # ... (fonksiyon içeriği aynı) ...
    logging.info(f"Genel web araması başlatıldı: '{query}'")
    if tavily_client:
        logging.debug("Web araması için Tavily deneniyor...")
        return search_web_tavily(query)
    else:
        # Tavily client yoksa veya başlatılamadıysa DDG kullan
        logging.debug("Tavily kullanılamıyor, web araması için DuckDuckGo deneniyor...")
        return search_web_duckduckgo(query)

# Web search tool tanımı (değişiklik yok)
web_search_tool = Tool(
    name="WebSearch",
    func=search_web,
    description="Çok güncel olaylar, haberler, hava durumu, hisse senedi fiyatları veya Wikipedia'da bulunmayan spesifik bilgiler için web'de arama yapar. En son bilgileri almak için kullanışlıdır."
)