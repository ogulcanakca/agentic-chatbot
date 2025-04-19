# app/travel_system/tools/parsing_tools.py

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any # Dict ve Any eklendi
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from app.core.llm import get_llm # LLM'i doğru yerden import ediyoruz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- Pydantic Modelini Güncelle ---
class TravelQuery(BaseModel):
    origin: Optional[str] = Field(None, description="The starting city or location of the trip, if specified (e.g., 'Istanbul', 'Izmir', 'Ayrancılar'). Defaults to null if not mentioned.") # <-- YENİ ALAN
    destination: str = Field(..., description="The city or place the user wants to travel to.")
    natural_language_date: str = Field(..., description="The user's description of the travel start date (e.g., 'next Wednesday', 'tomorrow', 'in 2 weeks', 'önümüzdeki ay başı').")
    duration_days: int = Field(..., description="The duration of the stay in days (e.g., '5 günlüğüne' means 5).")
    budget_amount: Optional[float] = Field(None, description="The user's approximate budget amount, if mentioned.")
    # Budget_currency için default kaldırdık, post-processing'de halledeceğiz
    budget_currency: Optional[str] = Field(None, description="The currency of the user's budget (e.g., TRY, EUR, USD, TL, lira), if mentioned. Defaults to null if not recognized.") 
    error: Optional[str] = Field(None, description="Error message if parsing fails or required info is missing.") # Hata alanı eklendi

# Tool fonksiyonu
@tool
def parse_travel_query(user_query: str) -> Dict[str, Any]:
    """
    Parses the user's natural language travel query to extract structured information 
    like origin, destination, date description, duration, and budget using an LLM.
    Normalizes common currency names/symbols to ISO 4217 codes. 
    If origin is not specified, defaults to 'Ayrancılar, İzmir'.
    """
    
    # LLM örneğini al ve structured output ile bağla
    llm_instance = get_llm(temperature=0.0) # Parsing için temperature 0
    if not llm_instance:
        logging.error("Parsing için LLM örneği alınamadı!")
        return {"error": "Sorgu ayrıştırma hizmeti şu an kullanılamıyor."}
        
    structured_llm = llm_instance.with_structured_output(TravelQuery)
    
    today_date_str = datetime.now().date().strftime('%Y-%m-%d')

    # --- Birincil Prompt'u Güncelle ---
    prompt = f"""
    Parse the following user query to extract travel details according to the TravelQuery schema.
    User Query: "{user_query}"

    Today's date is {today_date_str}. Use this for relative date context if needed, but extract the user's original phrase for 'natural_language_date'.
    
    **Extraction Instructions:**
    - **origin:** Extract the starting city if mentioned (e.g., 'from Istanbul', 'Ankara'dan', 'İzmir'den yola çıkıp...'). If not explicitly mentioned, leave the origin field null.
    - **destination:** Extract the destination city.
    - **natural_language_date:** Extract the user's description for the start date.
    - **duration_days:** Extract the duration in days. Convert phrases like 'bir hafta' to 7.
    - **budget_amount:** Extract the numerical budget amount.
    - **budget_currency:** Extract the currency. Normalize common names/symbols ('TL', 'lira', '€', '$', 'Pound', 'Sterlin' etc.) to 3-letter ISO codes (TRY, EUR, USD, GBP). If unclear or not mentioned, leave the budget_currency field null.
    - **error:** If required fields (destination, date, duration) are missing or ambiguous, set this field to a descriptive error message, but still try to extract other fields.

    **Output Format:** Only output the JSON object matching the TravelQuery schema. Do not include any other text.
    """

    logging.info(f"Parsing query with LLM: '{user_query}'")
    parsed_dict = None
    try:
        # Birincil ayrıştırmayı dene
        result = structured_llm.invoke(prompt)
        parsed_dict = result.model_dump(exclude_unset=True) # Sadece LLM'in set ettiklerini al
        logging.info(f"Structured parsing successful: {parsed_dict}")

    except Exception as e:
        logging.warning(f"Structured parsing failed: {e}. Trying fallback.", exc_info=True)
        # Yedek ayrıştırmayı dene (basit JSON isteme)
        fallback_prompt = f"""
        Parse the following user query and extract these details: origin, destination, natural_language_date, duration_days, budget_amount, budget_currency.
        Extract origin city if mentioned (e.g., 'from Istanbul'). If not mentioned, set origin to null.
        Normalize currency: 'TL', 'lira' -> 'TRY'; 'Euro', '€' -> 'EUR'; 'Dolar', '$' -> 'USD'; 'Sterlin', '£' -> 'GBP'. If currency is unclear or missing, set budget_currency to null.
        Output the result as a JSON object ONLY, without any surrounding text or markdown. Ensure keys are double-quoted.
        User Query: "{user_query}"
        Example Output: {{"origin": "Istanbul", "destination": "Paris", "natural_language_date": "next Wednesday", "duration_days": 2, "budget_amount": 10000, "budget_currency": "TRY"}}
        """
        try:
             response = llm_instance.invoke(fallback_prompt)
             content = response.content.strip()
             # LLM bazen markdown ```json ... ``` ekleyebilir, temizleyelim
             if content.startswith("```json"):
                 content = content[7:]
             if content.endswith("```"):
                 content = content[:-3]
             content = content.strip()
             parsed_dict = json.loads(content) # JSON'a çevir
             logging.info(f"Fallback parsing successful: {parsed_dict}")
        except Exception as fallback_e:
             logging.error(f"Fallback parsing also failed: {fallback_e}", exc_info=True)
             return {"error": f"Sorgu ayrıştırılamadı: {fallback_e}"}

    # --- Post-processing (Para birimi normalleştirme ve Varsayılan Origin) ---
    if parsed_dict:
        # Para birimi normalleştirme
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
            # else: tanınmıyorsa None kalır
        
        # Eğer bütçe miktarı varsa ama para birimi hala None ise TRY yap
        if parsed_dict.get("budget_amount") is not None and normalized_currency is None:
             normalized_currency = "TRY"
             
        # Güncellenmiş para birimini ekle (varsa)
        if normalized_currency:
            parsed_dict["budget_currency"] = normalized_currency
        elif "budget_currency" in parsed_dict: # Eğer normalize edilemediyse ve varsa, silelim
             del parsed_dict["budget_currency"]


        # Varsayılan Origin Ekleme
        if "origin" not in parsed_dict or not parsed_dict.get("origin"):
            default_origin = "Ayrancılar, İzmir" # Mevcut konumu kullan
            parsed_dict["origin"] = default_origin
            logging.info(f"Origin sorguda belirtilmemiş veya boş, varsayılan '{default_origin}' olarak ayarlandı.")
            
        # Eksik alan kontrolü (tekrar yapalım, fallback sonrası da gerekebilir)
        required_fields = ["destination", "natural_language_date", "duration_days"]
        missing_fields = [field for field in required_fields if not parsed_dict.get(field)]
        if missing_fields:
            error_msg = parsed_dict.get("error", f"Eksik bilgi: {', '.join(missing_fields)} belirtilmemiş veya anlaşılamadı.")
            parsed_dict["error"] = error_msg # Hata mesajını güncelle/ekle
            
        return parsed_dict
    else:
        # Bu duruma normalde gelinmemeli ama güvenlik için
        return {"error": "Sorgu ayrıştırma başarısız oldu (boş sonuç)."}