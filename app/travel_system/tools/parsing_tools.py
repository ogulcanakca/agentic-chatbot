# app/travel_system/tools/parsing_tools.py

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from app.core.llm import get_llm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- Pydantic Modeli (Aynı kalabilir) ---
class TravelQuery(BaseModel):
    origin: Optional[str] = Field(None, description="The starting city or location of the trip, if specified (e.g., 'Istanbul', 'Izmir', 'Ayrancılar'). Defaults to null if not mentioned.")
    destination: str = Field(..., description="The city or place the user wants to travel to.")
    natural_language_date: str = Field(..., description="The user's description of the travel start date (e.g., 'next Wednesday', 'tomorrow', 'in 2 weeks', 'önümüzdeki ay başı').")
    duration_days: int = Field(..., description="The duration of the stay in days. Extract the number from phrases like '3 gün', '5 günlüğüne', 'bir hafta (7 days)'.") # <-- AÇIKLAMA GÜNCELLENDİ
    budget_amount: Optional[float] = Field(None, description="The user's approximate budget amount, if mentioned.")
    budget_currency: Optional[str] = Field(None, description="The currency of the user's budget (e.g., TRY, EUR, USD, TL, lira), if mentioned. Defaults to null if not recognized.")
    error: Optional[str] = Field(None, description="Error message if parsing fails or required info is missing.")

# Tool fonksiyonu
@tool
def parse_travel_query(user_query: str) -> Dict[str, Any]:
    """
    Parses the user's natural language travel query to extract structured information
    like origin, destination, date description, duration, and budget using an LLM.
    Normalizes common currency names/symbols to ISO 4217 codes.
    If origin is not specified, defaults to 'Ayrancılar, İzmir'.
    """

    llm_instance = get_llm(temperature=0.0)
    if not llm_instance:
        logging.error("Parsing için LLM örneği alınamadı!")
        return {"error": "Sorgu ayrıştırma hizmeti şu an kullanılamıyor."}

    structured_llm = llm_instance.with_structured_output(TravelQuery)

    today_date_str = datetime.now().date().strftime('%Y-%m-%d')

    # --- Birincil Prompt'u Güncelle ---
    prompt = f"""
    Aşağıdaki kullanıcı sorgusunu analiz ederek TravelQuery şemasına göre seyahat detaylarını çıkarın.
    Kullanıcı Sorgusu: "{user_query}"

    Bugünün tarihi {today_date_str}. Bunu göreceli tarih bağlamı için kullanın, ancak 'natural_language_date' için kullanıcının orijinal ifadesini çıkarın.

    **Çıkarma Talimatları:**
    - **origin:** Eğer belirtilmişse başlangıç şehrini çıkarın (örn., 'from Istanbul', 'Ankara'dan', 'İzmir'den yola çıkıp...'). Açıkça belirtilmemişse, origin alanını null bırakın.
    - **destination:** Hedef şehri çıkarın.
    - **natural_language_date:** Başlangıç tarihi için kullanıcının açıklamasını çıkarın.
    - **duration_days:** Süreyi kesinlikle tam sayı gün olarak çıkarın.
        - 'bir hafta' 7 anlamına gelir.
        - '3 gün' veya '3 günlüğüne' veya '3 gün kalacağım' 3 anlamına gelir.
        - '5 gün' 5 anlamına gelir.
        'gün' veya 'hafta' ile ilişkili sayıya özellikle dikkat edin.
    - **budget_amount:** Sayısal bütçe miktarını çıkarın.
    - **budget_currency:** Para birimini çıkarın. Yaygın isim/sembolleri ('TL', 'lira', '€', '$', 'Pound', 'Sterlin' vb.) 3 harfli ISO kodlarına (TRY, EUR, USD, GBP) normalleştirin. Belirsiz veya belirtilmemişse, budget_currency alanını null bırakın.
    - **error:** Gerekli alanlar (destination, date, duration) eksik veya belirsizse, bu alana açıklayıcı bir hata mesajı koyun, ancak yine de diğer alanları çıkarmaya çalışın.

    **Çıktı Formatı:** Sadece TravelQuery şemasına uyan JSON nesnesini çıktılayın. Başka hiçbir metin eklemeyin.
    """ # <-- duration_days TALİMATI DETAYLANDIRILDI

    logging.info(f"Parsing query with LLM: '{user_query}'")
    parsed_dict = None
    try:
        result = structured_llm.invoke(prompt)
        parsed_dict = result.model_dump(exclude_unset=True)
        logging.info(f"Structured parsing successful: {parsed_dict}")

    except Exception as e:
        logging.warning(f"Structured parsing failed: {e}. Trying fallback.", exc_info=True)

        # --- Yedek (Fallback) Prompt'u Güncelle ---
        fallback_prompt = f"""
        Aşağıdaki kullanıcı sorgusunu analiz edin ve şu detayları çıkarın: origin, destination, natural_language_date, duration_days, budget_amount, budget_currency.
        Eğer belirtilmişse origin şehrini çıkarın (örn., 'Istanbul'dan'). Belirtilmemişse, origin değerini null olarak ayarlayın.
        duration_days için, gün sayısını tam sayı olarak çıkarın (örn., '3 gün' -> 3, 'bir hafta' -> 7).
        Para birimini normalleştirin: 'TL', 'lira' -> 'TRY'; 'Euro', '€' -> 'EUR'; 'Dolar', '$' -> 'USD'; 'Sterlin', '£' -> 'GBP'. Para birimi belirsiz veya eksikse, budget_currency değerini null olarak ayarlayın.
        Sonucu SADECE JSON nesnesi olarak çıktılayın, çevresinde herhangi bir metin veya markdown olmadan. Anahtarların çift tırnak içinde olduğundan emin olun.
        Kullanıcı Sorgusu: "{user_query}"
        Örnek Çıktı: {{"origin": "Istanbul", "destination": "Paris", "natural_language_date": "next Wednesday", "duration_days": 7, "budget_amount": 1500, "budget_currency": "EUR"}}
        """
        try:
            response = llm_instance.invoke(fallback_prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            parsed_dict = json.loads(content)
            logging.info(f"Fallback parsing successful: {parsed_dict}")
        except Exception as fallback_e:
            logging.error(f"Fallback parsing also failed: {fallback_e}", exc_info=True)
            return {"error": f"Sorgu ayrıştırılamadı: {fallback_e}"}

    # --- Post-processing (Aynı kalabilir) ---
    if parsed_dict:
        # Para birimi normalleştirme... (önceki kod gibi)
        raw_currency = parsed_dict.get("budget_currency")
        normalized_currency = None
        if raw_currency and isinstance(raw_currency, str):
            currency_lower = raw_currency.lower()
            if currency_lower in ["tl", "lira", "türk lirası", "try"]:
                normalized_currency = "TRY"
            elif currency_lower in ["euro", "eur", "€"]:
                normalized_currency = "EUR"
            elif currency_lower in ["dolar", "usd", "$"]:
                normalized_currency = "USD"
            elif currency_lower in ["sterlin", "pound", "gbp", "£"]:
                normalized_currency = "GBP"
            elif len(raw_currency) == 3: # Zaten ISO kodu olabilir
                 normalized_currency = raw_currency.upper()

        if parsed_dict.get("budget_amount") is not None and normalized_currency is None:
             normalized_currency = "TRY"

        if normalized_currency:
            parsed_dict["budget_currency"] = normalized_currency
        elif "budget_currency" in parsed_dict:
             del parsed_dict["budget_currency"]

        # Varsayılan Origin Ekleme... (önceki kod gibi)
        if "origin" not in parsed_dict or not parsed_dict.get("origin"):
            default_origin = "Ayrancılar, İzmir" # Mevcut konumu kullan
            parsed_dict["origin"] = default_origin
            logging.info(f"Origin sorguda belirtilmemiş veya boş, varsayılan '{default_origin}' olarak ayarlandı.")

        # Eksik alan kontrolü... (önceki kod gibi)
        required_fields = ["destination", "natural_language_date", "duration_days"]
        missing_fields = [field for field in required_fields if field not in parsed_dict or not parsed_dict.get(field)] # Kontrol güncellendi
        if missing_fields:
            error_msg = parsed_dict.get("error", f"Eksik bilgi: {', '.join(missing_fields)} belirtilmemiş veya anlaşılamadı.")
            parsed_dict["error"] = error_msg
            logging.warning(f"Parsing sonrası eksik alanlar: {missing_fields}") # Uyarı logu eklendi

        # DURATION KONTROLÜ (Ekstra Güvenlik)
        if "duration_days" not in parsed_dict or not isinstance(parsed_dict.get("duration_days"), int) or parsed_dict.get("duration_days", 0) <= 0:
             logging.error(f"Geçersiz veya sıfır 'duration_days' ayrıştırıldı: {parsed_dict.get('duration_days')}. Sorgu: '{user_query}'")
             # İsteğe bağlı: Hata mesajını burada da ayarlayabiliriz.
             # parsed_dict["error"] = parsed_dict.get("error", "") + " Geçersiz süre algılandı."
             # VEYA belki varsayılan bir süre atayabiliriz? Şimdilik loglamak yeterli.


        return parsed_dict
    else:
        return {"error": "Sorgu ayrıştırma başarısız oldu (boş sonuç)."}