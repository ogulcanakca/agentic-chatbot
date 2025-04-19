# app/travel_system/tools/budget_tools.py

import os # os modülünü import et
import requests
import json
import re
from typing import Optional, Dict, Any # Dict ve Any eklendi
from langchain_core.tools import tool
# Silinen config modülünden yapılan importu kaldırın:
# from config import llm, settings 

# Şehir-Para Birimi eşlemesi (bu kısım kalabilir veya genişletilebilir)
CITY_CURRENCY_MAP = {
    "paris": "EUR", "kyoto": "JPY", "london": "GBP", "new york": "USD",
    "istanbul": "TRY", "ankara": "TRY", "izmir": "TRY",
    # ... diğer şehirler eklenebilir
}

# Döviz kurları ve bütçe kontrolü için tool tanımı
@tool
def get_exchange_rates_and_budget(destination: str, budget_amount: Optional[float] = None, budget_currency: str = "TRY") -> Dict[str, Any]:
    """
    Verilen destinasyon için hedef para birimini belirler, temel döviz kurlarını 
    (TRY, EUR, USD'den hedef para birimine) alır ve eğer belirtilmişse 
    bütçenin yeterliliğini basitçe değerlendirir. 
    ExchangeRate-API kullanır.
    """
    # API anahtarını ortam değişkenlerinden al
    api_key = os.getenv("EXCHANGERATE_API_KEY")
    if not api_key:
        return {"error": "ExchangeRate-API anahtarı ortam değişkenlerinde bulunamadı."}

    # Destinasyonun para birimini bul
    destination_lower = destination.lower()
    target_currency = CITY_CURRENCY_MAP.get(destination_lower)
    
    if not target_currency:
        # Eğer haritada yoksa, genel bir varsayım yapmaya çalışabilir veya hata dönebiliriz
        # Şimdilik TRY olmayan yaygın para birimlerini deneyelim
        if "japonya" in destination_lower or "tokyo" in destination_lower or "kyoto" in destination_lower:
             target_currency = "JPY"
        elif "amerika" in destination_lower or "abd" in destination_lower or "new york" in destination_lower:
             target_currency = "USD"
        elif "ingiltere" in destination_lower or "london" in destination_lower:
             target_currency = "GBP"
        elif "euro" in destination_lower or "avrupa" in destination_lower or "paris" in destination_lower or "berlin" in destination_lower: # Geniş bir varsayım
             target_currency = "EUR"
        else:
             # Bulamazsak hata döndür
             return {"error": f"'{destination}' için hedef para birimi belirlenemedi. Haritaya eklenmesi gerekebilir."}

    base_currencies = ["TRY", "EUR", "USD"]
    # Hedef para birimi zaten base içindeyse, onu tekrar sorgulamaya gerek yok
    if target_currency in base_currencies:
        base_currencies.remove(target_currency)
        
    # Eğer hiç base currency kalmadıysa (örn. hedef TRY ise), sadece TRY/TRY=1 ekleyebiliriz.
    rates = {}
    if not base_currencies and target_currency == "TRY":
         rates["TRY"] = 1.0
         rates["EUR"] = None # Diğerlerini None olarak işaretle
         rates["USD"] = None
    elif not base_currencies:
         # Sadece hedef para birimi kaldıysa (örn. EUR hedef), EUR/EUR = 1 olur
         rates[target_currency] = 1.0
         
    # API URL'sini oluştur
    # Ücretsiz planda base değiştirilemediği için, USD tabanlı alıp çevireceğiz
    # url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    # Alternatif: API'nin desteklediği şekilde base currency ile sorgu atmak
    # (API dokümantasyonuna göre ayarlayın, aşağıdaki örnek USD tabanlıdır)
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"

    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTP hatalarını kontrol et (4xx, 5xx)
        data = response.json()

        if data.get("result") == "success":
            usd_rates = data.get("conversion_rates", {})
            
            # Hedef para biriminin USD karşısındaki kurunu al
            usd_to_target = usd_rates.get(target_currency)
            if usd_to_target is None:
                 return {"error": f"API yanıtında hedef para birimi '{target_currency}' için kur bulunamadı."}

            # İstenen base para birimlerinin hedef para birimine göre kurlarını hesapla
            for base in ["TRY", "EUR", "USD"]:
                if base == target_currency:
                     rates[base] = 1.0
                     continue
                
                usd_to_base = usd_rates.get(base)
                if usd_to_base is None:
                     rates[base] = None # Base kurunu bulamazsak None işaretle
                     logging.warning(f"USD'den {base} kuru API yanıtında bulunamadı.")
                else:
                     # Kur hesaplama: (USD / Base) * (Target / USD) = Target / Base
                     # VEYA: (Target / USD) / (Base / USD) 
                     # API USD tabanlı olduğu için: usd_to_target / usd_to_base = 1 BASE kaç TARGET eder
                     try:
                         rates[base] = usd_to_target / usd_to_base
                     except ZeroDivisionError:
                          rates[base] = None # Bölme hatası olursa
                          logging.error(f"Kur hesaplarken sıfıra bölme hatası: Base={base}")

            # Bütçe değerlendirmesi (çok basit)
            budget_evaluation = "Belirtilmedi"
            if budget_amount is not None:
                if budget_currency == target_currency:
                    converted_budget = budget_amount
                elif budget_currency in rates and rates[budget_currency] is not None:
                    # Bütçeyi hedef para birimine çevir: budget_amount * (target / budget_currency)
                    # Bizim hesapladığımız rate = (1 base = X target) olduğu için çarpmamız gerekir
                    converted_budget = budget_amount * rates[budget_currency]
                else:
                    converted_budget = None
                    budget_evaluation = f"{budget_currency} kuru bulunamadığı için değerlendirilemedi."

                if converted_budget is not None:
                     # Bu değerlendirme çok kaba, geliştirilebilir
                     if converted_budget < 100: # Örnek eşik değer (hedef para biriminde)
                          budget_evaluation = f"Bütçe ({converted_budget:.2f} {target_currency}) çok düşük görünüyor."
                     elif converted_budget < 500:
                          budget_evaluation = f"Bütçe ({converted_budget:.2f} {target_currency}) kısıtlı olabilir."
                     else:
                          budget_evaluation = f"Bütçe ({converted_budget:.2f} {target_currency}) makul görünüyor."
                     
            formatted_rates = {f"1 {cur}": f"{rate:.4f} {target_currency}" if rate is not None else "N/A" for cur, rate in rates.items()}

            return {
                "target_currency": target_currency,
                "rates": formatted_rates,
                "budget_evaluation": budget_evaluation,
                "raw_rates" : rates # Hesaplama için ham kurları da döndürelim
            }
        else:
            error_type = data.get("error-type", "Bilinmeyen API hatası")
            logging.error(f"ExchangeRate-API Hatası: {error_type}")
            return {"error": f"Döviz kuru API hatası: {error_type}"}

    except requests.exceptions.RequestException as e:
        logging.error(f"Döviz kuru API'sine bağlanırken hata: {e}", exc_info=True)
        return {"error": f"Döviz kuru API'sine bağlanılamadı: {e}"}
    except Exception as e:
        logging.error(f"Döviz kuru alınırken beklenmedik hata: {e}", exc_info=True)
        return {"error": f"Döviz kuru alınırken hata: {e}"}