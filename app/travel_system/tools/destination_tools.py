# app/travel_system/tools/destination_tools.py

import os
import requests
import json
import logging
from datetime import datetime
from urllib.parse import quote
from typing import Optional, Dict, Any
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
        return f"Şehir bilgisi aranırken bir hata oluştu: {e}"

# --- get_coordinates (Yardımcı Fonksiyon) ---
def get_coordinates(city_name: str, api_key: str) -> Dict[str, Any]:
    """Gets latitude and longitude for a city using OpenWeatherMap Geocoding API."""
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
             lat = float(data[0].get('lat', 0.0))
             lon = float(data[0].get('lon', 0.0))
             logging.debug(f"Koordinatlar bulundu: Lat={lat}, Lon={lon}")
             return {"lat": lat, "lon": lon}
        else:
             logging.warning(f"OpenWeatherMap Geocoding API '{city_name}' şehrini bulamadı veya boş yanıt döndü.")
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
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logging.error("OPENWEATHERMAP_API_KEY ortam değişkeni bulunamadı.")
        return "Hata: Hava durumu API anahtarı bulunamadı."

    logging.info(f"OpenWeatherMap ile '{city_name}' için {start_date_str} - {end_date_str} arası hava durumu aranıyor...")
    coords = get_coordinates(city_name, api_key)
    if "error" in coords:
        logging.error(f"Koordinatlar alınamadı: {coords['error']}")
        return f"Hata: {coords['error']}"

    base_url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {
        'lat': coords['lat'],
        'lon': coords['lon'],
        'appid': api_key,
        'units': 'metric',
        'lang': 'tr'
    }
    forecast_summary = f"Hava durumu özeti alınamadı ({city_name})."
    relevant_forecasts_str = "Detaylı tahmin bulunamadı."

    try:
        response = requests.get(base_url, params=params)
        logging.debug(f"OpenWeatherMap API Yanıt Kodu: {response.status_code}")
        response.raise_for_status()
        weather_data = response.json()
        logging.debug(f"OpenWeatherMap Ham Yanıt: {json.dumps(weather_data, indent=2, ensure_ascii=False)}")

        if str(weather_data.get("cod")) != "200":
             message = weather_data.get("message", "Bilinmeyen API hatası")
             logging.error(f"OpenWeatherMap API Hatası (cod != 200): {message}")
             return f"Hava durumu alınamadı: {message}"

        forecast_summary = f"{city_name} için {start_date_str} - {end_date_str} Hava Durumu Özeti:\n"
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            logging.error(f"Geçersiz tarih formatı: {start_date_str} veya {end_date_str}")
            return "Hata: Geçersiz tarih formatı (YYYY-MM-DD bekleniyor)."

        relevant_forecasts = []
        if 'list' in weather_data and isinstance(weather_data['list'], list):
            for forecast in weather_data['list']:
                 try:
                     forecast_dt = datetime.fromtimestamp(int(forecast.get('dt', 0)))
                     forecast_date = forecast_dt.date()
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
                     continue

            relevant_forecasts = sorted(list(set(relevant_forecasts)))

        if not relevant_forecasts:
            relevant_forecasts_str = "Belirtilen tarihler için detaylı tahmin bulunamadı (API 5 günlük veri sağlar).\n"
            logging.warning(relevant_forecasts_str)
        else:
            relevant_forecasts_str = "\n".join(relevant_forecasts) + "\n"
            logging.info("İlgili hava durumu tahminleri işlendi.")

        forecast_summary += relevant_forecasts_str
        logging.info("Hava durumu özeti için kıyafet önerisi LLM'den isteniyor...")
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
                response = llm_instance.invoke(prompt)
                suggestion_text = response.content.strip()
                logging.info(f"LLM'den kıyafet önerisi alındı: {suggestion_text}")
            except Exception as llm_err:
                logging.error(f"LLM kıyafet önerisi alırken hata: {llm_err}", exc_info=True)
                suggestion_text = f"Kıyafet önerisi alınırken bir LLM hatası oluştu."

        final_output = forecast_summary.strip() + "\n\nKıyafet Önerileri:\n" + suggestion_text
        logging.info("get_weather_forecast aracı tamamlandı ve string sonuç döndürüyor.")
        return final_output

    except requests.exceptions.RequestException as e:
        logging.error(f"OpenWeatherMap API'sine bağlanırken hata: {e}", exc_info=True)
        return f"Hata: Hava durumu API'sine bağlanılamadı: {e}"
    except Exception as e:
        logging.error(f"Hava durumu alınırken veya işlenirken beklenmedik hata: {e}", exc_info=True)
        return f"Hata: Hava durumu alınırken veya işlenirken beklenmedik bir sorun oluştu: {e}"


# --- Search Hotel Booking Links (Replaced Google Hotels_with_tavily) ---
@tool
def search_hotel_booking_links(destination: str, start_date: str, end_date: str, budget_info: Optional[str] = None) -> str:
    """
    Uses Tavily Search API to find links to popular hotel booking websites
    (like Google Hotels, Booking.com, Expedia) for the specified destination and dates.
    Does NOT return specific hotel recommendations.
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        logging.error("TAVILY_API_KEY environment variable not found.")
        return "Hata: Otel arama API anahtarı (Tavily) bulunamadı."

    logging.info(f"Searching for hotel booking links via Tavily: Dest={destination}, Dates={start_date}-{end_date}")

    # Query focusing on finding booking sites
    query = f"hotel booking websites for {destination} check-in {start_date} check-out {end_date}"
    # Optional: Add budget context if available
    # if budget_info and "N/A" not in budget_info and "Belirtilmedi" not in budget_info:
    #     query += f" budget {budget_info}" # Keep it simple for link finding

    logging.debug(f"Tavily Hotel Link Search Query: {query}")

    try:
        # Get a few search results
        tavily_search = TavilySearchResults(max_results=4) # Get slightly more results
        results = tavily_search.invoke({"query": query}) # Results should be like [{url: ..., content: ...}, ...]

        if not results or not isinstance(results, list):
            logging.warning("Tavily hotel link search returned no results or unexpected format.")
            return f"{destination} için ilgili otel rezervasyon sitesi linkleri Tavily araması ile bulunamadı."

        # Extract and format URLs from results
        links_found = []
        processed_urls = set() # To avoid duplicate domains (optional)
        known_sites = ["booking.com", "expedia", "google.com/travel/hotels", "hotels.com", "agoda.com", "trivago"]

        for result in results:
            if isinstance(result, dict) and result.get("url"):
                url = result.get("url")
                # Basic check for known booking sites or if it contains 'hotel'
                is_relevant = False
                for site in known_sites:
                    if site in url:
                        is_relevant = True
                        break
                if not is_relevant and "hotel" in url: # Broader check
                     is_relevant = True

                if is_relevant:
                    # Optional: Extract domain to avoid duplicates like www.booking.com and m.booking.com
                    try:
                        domain = url.split('/')[2].replace('www.', '')
                        if domain not in processed_urls:
                            title = result.get("title", url) # Use title if available
                            links_found.append(f"- {title}: {url}")
                            processed_urls.add(domain)
                    except IndexError:
                         # Fallback if URL format is unexpected
                         if url not in processed_urls: # Check full url if domain extraction fails
                             title = result.get("title", url)
                             links_found.append(f"- {title}: {url}")
                             processed_urls.add(url)


        if not links_found:
             logging.warning("Tavily results processed, but no relevant links extracted based on filters.")
             return f"{destination} için ilgili otel rezervasyon sitesi linkleri Tavily sonuçlarından çıkarılamadı."

        logging.info("Found relevant hotel booking links via Tavily.")
        # Combine links into the final string
        return f"Otel aramak için kullanabileceğiniz bazı linkler:\n" + "\n".join(links_found)

    except Exception as e:
        logging.error(f"Error during Tavily hotel link search: {e}", exc_info=True)
        return f"Otel arama linkleri aranırken bir sorun oluştu: {e}"


# --- get_tomtom_coordinates (Yardımcı Fonksiyon) ---
def get_tomtom_coordinates(city_name: str, api_key: str) -> Dict[str, Any]:
    """Helper function to get coordinates using TomTom Search API."""
    if not api_key:
        logging.error("get_tomtom_coordinates çağrılırken API anahtarı eksik.")
        return {"error": "TomTom API anahtarı eksik."}

    logging.debug(f"TomTom Search API ile '{city_name}' koordinatları alınıyor...")
    encoded_city = quote(city_name)
    url = f"https://api.tomtom.com/search/2/geocode/{encoded_city}.json?key={api_key}&limit=1"

    try:
        response = requests.get(url)
        logging.debug(f"TomTom Geocoding Yanıt Kodu: {response.status_code}, Yanıt: {response.text[:200]}...")
        response.raise_for_status()
        data = response.json()

        if data and data.get('results') and isinstance(data['results'], list) and len(data['results']) > 0:
            position = data['results'][0].get('position')
            if position and isinstance(position, dict) and 'lat' in position and 'lon' in position:
                 try:
                     lat = float(position['lat'])
                     lon = float(position['lon'])
                     logging.debug(f"TomTom koordinatları bulundu: Lat={lat}, Lon={lon}")
                     return {"lat": lat, "lon": lon}
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
        logging.error(f"TomTom koordinatları alınırken/işlenirken beklenmedik hata: {e}", exc_info=True)
        return {"error": f"Harita koordinatları alınırken beklenmedik bir sorun oluştu (TomTom): {e}"}

# --- get_tomtom_map_url ---
@tool
def get_tomtom_map_url(city_name: str) -> str:
    """
    Belirtilen şehir için TomTom Map Display API kullanarak statik bir harita
    görseli URL'si oluşturur. TOMTOM_API_KEY ortam değişkeni gereklidir.
    """
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        logging.error("TOMTOM_API_KEY ortam değişkeni bulunamadı.")
        return "Hata: Harita oluşturmak için gerekli API anahtarı (TomTom) bulunamadı."

    coords = get_tomtom_coordinates(city_name, api_key)
    if "error" in coords:
        logging.error(f"Harita URL'si için koordinatlar alınamadı: {coords['error']}")
        return f"Hata: Harita için konum bilgisi alınamadı ({city_name}). Sebep: {coords['error']}"

    lat = coords['lat']
    lon = coords['lon']
    zoom = 11
    width = 600
    height = 400
    img_format = "png"
    map_url = f"https://api.tomtom.com/map/1/staticimage?key={api_key}&center={lon},{lat}&zoom={zoom}&width={width}&height={height}&format={img_format}"

    logging.info(f"TomTom statik harita URL'si oluşturuldu: {city_name}")
    return map_url