# app/travel_system/tools/destination_tools.py

import os
import requests
import json
import logging
from datetime import datetime
from urllib.parse import quote 
from typing import Optional, Dict, Any # Optional, Dict, Any import edildiğinden emin olun
from langchain_core.tools import tool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.tools.tavily_search import TavilySearchResults
# Doğru LLM fonksiyonunu import et
from app.core.llm import get_llm 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- search_city_info ---
@tool
def search_city_info(city_name: str) -> str:
    """
    Verilen şehir hakkında genel bilgileri, turistik yerleri vb. 
    Google Serper API kullanarak arar.
    """
    # API Anahtarını ortam değişkeninden al ve kontrol et
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        logging.error("SERPER_API_KEY ortam değişkeni bulunamadı.")
        # Hata durumunda None yerine açıklayıcı string döndür
        return "Hata: Şehir bilgisi arama API anahtarı (Serper) bulunamadı."
        
    logging.info(f"Google Serper API ile '{city_name}' hakkında bilgi aranıyor...")
    try:
        search = GoogleSerperAPIWrapper(serper_api_key=serper_api_key) # Anahtarı doğrudan ver
        query = f"{city_name} hakkında genel bilgi, turistik yerler, popüler mekanlar"
        results = search.run(query) 
        logging.info(f"Google Serper API'den sonuç alındı.")
        # Sonuç yoksa veya boşsa belirt
        return results if results else f"'{city_name}' hakkında Google Serper ile bilgi bulunamadı."
    except Exception as e:
        logging.error(f"Google Serper API araması sırasında hata: {e}", exc_info=True)
        # Hata durumunda açıklayıcı string döndür
        return f"Şehir bilgisi aranırken bir hata oluştu: {e}"

# --- get_coordinates (Yardımcı Fonksiyon) ---
# Bu fonksiyon @tool ile işaretlenmemeli, sadece get_weather_forecast tarafından kullanılır.
def get_coordinates(city_name: str, api_key: str) -> Dict[str, Any]:
    """Gets latitude and longitude for a city using OpenWeatherMap Geocoding API."""
    # Bu fonksiyon içindeki API anahtarı kontrolü kaldırıldı, çağıran fonksiyon kontrol edecek.
    logging.debug(f"OpenWeatherMap Geocoding ile '{city_name}' koordinatları alınıyor...")
    base_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        'q': city_name,
        'limit': 1,
        'appid': api_key
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
             # Koordinatları float olarak almayı dene
             lat = float(data[0].get('lat', 0.0))
             lon = float(data[0].get('lon', 0.0))
             logging.debug(f"Koordinatlar bulundu: Lat={lat}, Lon={lon}")
             return {"lat": lat, "lon": lon}
        else:
             logging.warning(f"OpenWeatherMap Geocoding API '{city_name}' şehrini bulamadı veya boş yanıt döndü.")
             # Hata durumunda dictionary döndür
             return {"error": f"OpenWeatherMap Geocoding API '{city_name}' şehrini bulamadı."}
    except requests.exceptions.RequestException as e:
         logging.error(f"OpenWeatherMap Geocoding API'sine bağlanırken hata: {e}", exc_info=True)
         return {"error": f"Hava durumu koordinatları alınamadı (bağlantı hatası): {e}"}
    except (ValueError, KeyError, IndexError) as e:
         logging.error(f"OpenWeatherMap Geocoding API yanıtı işlenirken hata: {e}", exc_info=True)
         return {"error": f"Hava durumu koordinatları alınamadı (yanıt formatı hatası): {e}"}
    except Exception as e:
        logging.error(f"Koordinat alınırken beklenmedik hata: {e}", exc_info=True)
        return {"error": f"Koordinat alınırken beklenmedik bir hata oluştu: {e}"}


# --- get_weather_forecast ---
@tool
def get_weather_forecast(city_name: str, start_date_str: str, end_date_str: str) -> str:
    """
    Belirtilen şehir ve tarihler (YYYY-MM-DD) için OpenWeatherMap API (5 günlük) 
    kullanarak hava durumu tahminini alır ve LLM kullanarak Türkçe kıyafet önerisi sunar.
    """
    # API Anahtarını ortam değişkeninden al ve kontrol et
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logging.error("OPENWEATHERMAP_API_KEY ortam değişkeni bulunamadı.")
        return "Hata: Hava durumu API anahtarı bulunamadı." 

    logging.info(f"OpenWeatherMap ile '{city_name}' için {start_date_str} - {end_date_str} arası hava durumu aranıyor...")

    # Koordinatları al
    coords = get_coordinates(city_name, api_key)
    if "error" in coords:
        logging.error(f"Koordinatlar alınamadı: {coords['error']}")
        # Koordinat hatasını doğrudan döndür
        return f"Hata: {coords['error']}" 

    # Hava durumu verilerini çekiyoruz (Forecast endpoint)
    base_url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {
        'lat': coords['lat'],
        'lon': coords['lon'],
        'appid': api_key,
        'units': 'metric',
        'lang': 'tr'
    }
    
    forecast_summary = f"Hava durumu özeti alınamadı ({city_name})." # Varsayılan
    relevant_forecasts_str = "Detaylı tahmin bulunamadı." # Varsayılan

    try:
        response = requests.get(base_url, params=params)
        logging.debug(f"OpenWeatherMap API Yanıt Kodu: {response.status_code}")
        response.raise_for_status()
        weather_data = response.json()
        logging.debug(f"OpenWeatherMap Ham Yanıt: {json.dumps(weather_data, indent=2, ensure_ascii=False)}")

        if str(weather_data.get("cod")) != "200": # cod string dönebilir
             message = weather_data.get("message", "Bilinmeyen API hatası")
             logging.error(f"OpenWeatherMap API Hatası (cod != 200): {message}")
             return f"Hava durumu alınamadı: {message}"

        forecast_summary = f"{city_name} için {start_date_str} - {end_date_str} Hava Durumu Özeti:\n"
        
        # Tarihleri parse et (hata kontrolü eklendi)
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
             logging.error(f"Geçersiz tarih formatı: {start_date_str} veya {end_date_str}")
             return "Hata: Geçersiz tarih formatı (YYYY-MM-DD bekleniyor)."

        relevant_forecasts = []
        if 'list' in weather_data and isinstance(weather_data['list'], list):
            for forecast in weather_data['list']:
                 try: # Her bir forecast elemanını işlerken hata olursa atla
                      forecast_dt = datetime.fromtimestamp(int(forecast.get('dt', 0))) # dt int olmalı
                      forecast_date = forecast_dt.date()
                      # İlgili tarih aralığı ve öğlen saatleri kontrolü
                      if start_date <= forecast_date <= end_date and 11 <= forecast_dt.hour <= 14:
                           desc = forecast.get('weather',[{}])[0].get('description','bilgi yok').capitalize()
                           temp = forecast.get('main',{}).get('temp','?')
                           feels = forecast.get('main',{}).get('feels_like','?')
                           hum = forecast.get('main',{}).get('humidity','?')
                           wind = forecast.get('wind',{}).get('speed','?')
                           relevant_forecasts.append(
                                f"- {forecast_date.strftime('%Y-%m-%d %A')}: {desc}, "
                                f"Sıcaklık: {temp}°C (Hissedilen: {feels}°C), "
                                f"Nem: %{hum}, Rüzgar: {wind} m/s"
                           )
                 except (KeyError, IndexError, ValueError, TypeError) as item_err:
                      logging.warning(f"Hava durumu listesi elemanı işlenirken hata atlandı: {item_err} - Veri: {forecast}")
                      continue # Bu elemanı atla, diğerlerine devam et

            # Tekrarları kaldır
            relevant_forecasts = sorted(list(set(relevant_forecasts)))
        
        if not relevant_forecasts:
             relevant_forecasts_str = "Belirtilen tarihler için detaylı tahmin bulunamadı (API 5 günlük veri sağlar).\n"
             logging.warning(relevant_forecasts_str)
        else:
             relevant_forecasts_str = "\n".join(relevant_forecasts) + "\n"
             logging.info("İlgili hava durumu tahminleri işlendi.")
        
        forecast_summary += relevant_forecasts_str # Özeti oluştur

        # Kıyafet önerisi için LLM'i kullan
        logging.info("Hava durumu özeti için kıyafet önerisi LLM'den isteniyor...")
        # LLM örneğini get_llm ile al ve None kontrolü yap
        llm_instance = get_llm(temperature=0.3) 
        if not llm_instance:
            logging.error("Kıyafet önerisi için LLM örneği alınamadı.")
            suggestion_text = "Kıyafet önerisi sistem hatası nedeniyle oluşturulamadı."
        else:
            prompt = f"""Aşağıdaki hava durumu özeti verildiğinde, Türkiye'de yaşayan birisi için Türkçe olarak pratik ve kısa kıyafet önerileri sunar mısın? Sadece kıyafet önerilerine odaklan, hava durumunu tekrarlama. Örnek: "Yanınıza katmanlı giysiler, ince bir mont ve şemsiye almanız iyi olur." gibi.

Hava Durumu Özeti:
{relevant_forecasts_str}

Kıyafet Önerileri:"""
            logging.debug(f"Kıyafet önerisi için LLM Prompt'u:\n{prompt}")
            try:
                 # LLM çağrısını da try-except içine al
                 response = llm_instance.invoke(prompt)
                 suggestion_text = response.content.strip()
                 logging.info(f"LLM'den kıyafet önerisi alındı: {suggestion_text}")
            except Exception as llm_err:
                 logging.error(f"LLM kıyafet önerisi alırken hata: {llm_err}", exc_info=True)
                 suggestion_text = f"Kıyafet önerisi alınırken bir LLM hatası oluştu." 

        # Hem hava durumunu hem de öneriyi birleştirerek tek bir string döndür
        final_output = forecast_summary.strip() + "\n\nKıyafet Önerileri:\n" + suggestion_text
        logging.info("get_weather_forecast aracı tamamlandı ve string sonuç döndürüyor.")
        return final_output # <-- STRING DÖNDÜRÜYOR

    except requests.exceptions.RequestException as e:
        logging.error(f"OpenWeatherMap API'sine bağlanırken hata: {e}", exc_info=True)
        return f"Hata: Hava durumu API'sine bağlanılamadı: {e}" 
    except Exception as e:
        logging.error(f"Hava durumu alınırken veya işlenirken beklenmedik hata: {e}", exc_info=True)
        return f"Hata: Hava durumu alınırken veya işlenirken beklenmedik bir sorun oluştu: {e}"


# --- Google Hotels_with_tavily ---
@tool
def Google_Hotels_with_tavily(destination: str, start_date: str, end_date: str, budget_info: Optional[str] = None) -> str:
    """
    Uses Tavily Search API to simulate searching for hotels on Google Hotels 
    for a specific destination, dates (YYYY-MM-DD), and optional budget info.
    """
    # API anahtarını kontrol et (TavilySearchResults kendi de kontrol edebilir)
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
         logging.error("TAVILY_API_KEY ortam değişkeni bulunamadı.")
         return "Hata: Otel arama API anahtarı (Tavily) bulunamadı."
         
    logging.info(f"Tavily ile Google Hotels araması simüle ediliyor: Dest={destination}, Tarih={start_date}-{end_date}, Bütçe={budget_info}")
    
    query = f"Google Hotels search for {destination} from {start_date} to {end_date}"
    if budget_info and "N/A" not in budget_info and "Belirtilmedi" not in budget_info: # Bütçe varsa ekle
        # Bütçe bilgisini sorguya daha anlamlı ekleyelim
        query += f" suitable for a budget around {budget_info}"
    query += ". Include price ranges, ratings, and location if possible."
    logging.debug(f"Tavily Otel Arama Sorgusu: {query}")
    
    try:
        # Tavily aracını başlat
        # Not: include_answer=True daha özetleyici bir cevap verebilir
        tavily_search = TavilySearchResults(max_results=5) 
        results = tavily_search.invoke({"query": query})
        
        if results:
            logging.info("Tavily otel araması sonuç döndürdü.")
            # Sonucu olduğu gibi döndür, agent yorumlasın
            return f"Otel Arama Sonuçları (Tavily):\n{results}"
        else:
            logging.warning("Tavily otel araması sonuç döndürmedi.")
            return "Otel Arama Sonuçları (Tavily): Belirtilen kriterlere uygun otel bilgisi bulunamadı."
            
    except Exception as e:
        logging.error(f"Tavily otel araması sırasında hata: {e}", exc_info=True)
        return f"Otel araması sırasında bir sorun oluştu: {e}"
    
# Önce koordinatları almak için yardımcı fonksiyon (TomTom Search API ile)
def get_tomtom_coordinates(city_name: str, api_key: str) -> Dict[str, Any]:
    """Helper function to get coordinates using TomTom Search API."""
    # API anahtarı kontrolü burada tekrar yapılabilir veya çağıran fonksiyonda yapılır.
    if not api_key: 
        # Bu yardımcı fonksiyon olduğu için hata loglayıp None dönmek yerine 
        # hata dictionary'si döndürmek daha iyi olabilir.
        logging.error("get_tomtom_coordinates çağrılırken API anahtarı eksik.")
        return {"error": "TomTom API anahtarı eksik."}

    logging.debug(f"TomTom Search API ile '{city_name}' koordinatları alınıyor...")
    encoded_city = quote(city_name) # Şehir adını URL için güvenli hale getir
    # TomTom Geocoding API Endpoint v2
    url = f"https://api.tomtom.com/search/2/geocode/{encoded_city}.json?key={api_key}&limit=1"
    
    try:
        response = requests.get(url)
        # Yanıtı logla (debug için)
        logging.debug(f"TomTom Geocoding Yanıt Kodu: {response.status_code}, Yanıt: {response.text[:200]}...") # Yanıtın başını logla
        response.raise_for_status() # HTTP hatası varsa exception fırlat
        data = response.json()
        
        # Yanıtın beklenen formatta olup olmadığını kontrol et
        if data and data.get('results') and isinstance(data['results'], list) and len(data['results']) > 0:
            position = data['results'][0].get('position')
            # Pozisyon bilgisinin ve lat/lon'un varlığını kontrol et
            if position and isinstance(position, dict) and 'lat' in position and 'lon' in position:
                 try:
                     # Değerleri float'a çevirmeyi dene
                     lat = float(position['lat'])
                     lon = float(position['lon'])
                     logging.debug(f"TomTom koordinatları bulundu: Lat={lat}, Lon={lon}")
                     return {"lat": lat, "lon": lon} # Başarılı sonuç
                 except (ValueError, TypeError) as conv_err:
                      logging.error(f"TomTom koordinatları sayıya çevrilemedi: {conv_err} - Veri: {position}")
                      return {"error": f"TomTom API'den geçersiz koordinat formatı alındı."}
            else:
                 logging.warning(f"TomTom Geocoding API yanıtında 'position' veya 'lat'/'lon' bulunamadı. Yanıt: {data}")
                 return {"error": f"TomTom API '{city_name}' için koordinat pozisyonu bulamadı (detaylı yanıt formata bakın)."}
        else:
            logging.warning(f"TomTom Search API '{city_name}' için koordinat bulamadı veya geçersiz yanıt. Yanıt: {data}")
            return {"error": f"TomTom API '{city_name}' için koordinat bulamadı (geçersiz yanıt)."}
            
    except requests.exceptions.RequestException as e:
        logging.error(f"TomTom Search API'sine bağlanırken hata: {e}", exc_info=True)
        return {"error": f"Harita koordinatları alınamadı (TomTom bağlantı hatası): {e}"}
    except json.JSONDecodeError as e:
         logging.error(f"TomTom Search API yanıtı JSON olarak çözümlenemedi: {e}. Yanıt Metni: {response.text[:200]}...")
         return {"error": f"Harita koordinatları alınamadı (TomTom API yanıt formatı hatası)."}
    except Exception as e:
        # Diğer beklenmedik hatalar
        logging.error(f"TomTom koordinatları alınırken/işlenirken beklenmedik hata: {e}", exc_info=True)
        return {"error": f"Harita koordinatları alınırken beklenmedik bir sorun oluştu (TomTom): {e}"}

# Asıl Langchain Aracı (@tool ile işaretlenmiş)
@tool
def get_tomtom_map_url(city_name: str) -> str:
    """
    Belirtilen şehir için TomTom Map Display API kullanarak statik bir harita 
    görseli URL'si oluşturur. TOMTOM_API_KEY ortam değişkeni gereklidir.
    """
    # TomTom API anahtarını al
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        logging.error("TOMTOM_API_KEY ortam değişkeni bulunamadı.")
        # Agent'a hatayı bildir
        return "Hata: Harita oluşturmak için gerekli API anahtarı (TomTom) bulunamadı."

    # Yardımcı fonksiyonu kullanarak koordinatları al
    coords = get_tomtom_coordinates(city_name, api_key)
    # Koordinatlar alınırken hata oluştuysa, hata mesajını döndür
    if "error" in coords:
        logging.error(f"Harita URL'si için koordinatlar alınamadı: {coords['error']}")
        return f"Hata: Harita için konum bilgisi alınamadı ({city_name}). Sebep: {coords['error']}"
        
    # Koordinatları al
    lat = coords['lat']
    lon = coords['lon']
    
    # Statik Harita URL'sini oluşturmak için parametreler
    zoom = 11      # Şehir geneli görünümü için uygun bir zoom seviyesi
    width = 600    # Piksel cinsinden genişlik
    height = 400   # Piksel cinsinden yükseklik
    img_format = "png" # Resim formatı (png veya jpg olabilir)
    
    # TomTom Static Image API v1 URL formatı
    # Dökümantasyon: https://developer.tomtom.com/map-display-api/documentation/static-image/static-image
    map_url = f"https://api.tomtom.com/map/1/staticimage?key={api_key}&center={lon},{lat}&zoom={zoom}&width={width}&height={height}&format={img_format}"
    
    logging.info(f"TomTom statik harita URL'si oluşturuldu: {city_name}")
    # Başarı durumunda oluşturulan URL'yi string olarak döndür
    return map_url