# tools/parsing_tools.py

from datetime import datetime
import json
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.tools import tool
from app.core.llm import get_llm

# Kullanıcı sorgusundan çıkaracağımız seyahat verilerini temsil eden model tanımlıyoruz
class TravelQuery(BaseModel):
    destination: str = Field(description="The city or place the user wants to travel to.")
    natural_language_date: str = Field(description="The user's description of the travel start date (e.g., 'next Wednesday', 'tomorrow', 'in 2 weeks', 'önümüzdeki ay başı').")
    duration_days: int = Field(description="The duration of the stay in days (e.g., '5 günlüğüne' means 5).")
    budget_amount: Optional[float] = Field(description="The user's approximate budget amount, if mentioned.", default=None)
    budget_currency: Optional[str] = Field(description="The currency of the user's budget (e.g., TRY, EUR, USD, TL, lira), if mentioned.", default="TRY")

# Kullanıcının doğal dildeki seyahat sorgusunu yapılandırılmış bilgiye dönüştürüyoruz
@tool
def parse_travel_query(user_query: str) -> dict:
    """
    Parses the user's natural language travel query to extract structured information
    like destination, date description, duration, and budget using an settings.llm.
    Normalizes common currency names/symbols to ISO 4217 codes.
    """
    structured_llm = get_llm().with_structured_output(TravelQuery)

    # LLM'e sorguyu nasıl ayrıştıracağını açıklayan prompt hazırlıyoruz
    prompt = f"""
    Parse the following user query to extract travel details according to the TravelQuery schema.
    User Query: "{user_query}"

    Today's date is {datetime.now().date().strftime('%Y-%m-%d')}. Use this for relative date context if needed, but extract the user's original phrase for 'natural_language_date'.
    If budget is mentioned, try to extract both the amount and the currency.
    Normalize recognized currency names or symbols to their 3-letter ISO 4217 code:
    - Turkish Lira indicators ('TL', 'lira', 'Türk Lirası') should become 'TRY'.
    - Euro indicators ('Euro', 'EUR', '€') should become 'EUR'.
    - US Dollar indicators ('Dolar', 'USD', '$') should become 'USD'.
    - British Pound indicators ('Sterlin', 'Pound', 'GBP', '£') should become 'GBP'.
    If only an amount is given and context suggests Turkish Lira, use 'TRY'. If no currency is mentioned or recognizable, default to 'TRY'.
    For duration, convert phrases like 'bir hafta', '5 günlüğüne' to the number of days.
    """
    result = structured_llm.invoke(prompt)
    parsed_dict = result.model_dump()

    # Para birimi kodlarını standartlaştırıyoruz. (Gereksiz LLM çağrıları yapmamak için koşula bağlı ilk adım tasarladım)
    if parsed_dict.get("budget_currency"):
        currency_lower = parsed_dict["budget_currency"].lower()
        if currency_lower in ["tl", "lira", "türk lirası"]:
            parsed_dict["budget_currency"] = "TRY"
        elif currency_lower in ["euro", "eur", "€"]:
            parsed_dict["budget_currency"] = "EUR"
        elif currency_lower in ["dolar", "usd", "$"]:
            parsed_dict["budget_currency"] = "USD"
        elif currency_lower in ["sterlin", "pound", "gbp", "£"]:
                parsed_dict["budget_currency"] = "GBP"
        else:
                parsed_dict["budget_currency"] = parsed_dict["budget_currency"].upper()

        if not parsed_dict.get("budget_currency") and parsed_dict.get("budget_amount") is not None:
             parsed_dict["budget_currency"] = "TRY"

        return parsed_dict
    
    # Yapılandırılmış çıktı başarısız olursa, yedek çözüm kullanıyoruz. 
    fallback_prompt = f"""
    Parse the following user query and extract the key travel details: destination, natural_language_date, duration_days, budget_amount, budget_currency.
    Normalize currency: 'TL', 'lira' -> 'TRY'; 'Euro', '€' -> 'EUR'; 'Dolar', '$' -> 'USD'; 'Sterlin', '£' -> 'GBP'. Default to 'TRY' if unspecified.
    Output the result as a JSON object ONLY, without any surrounding text or markdown.
    User Query: "{user_query}"
    Example Output: {{"destination": "Paris", "natural_language_date": "next Wednesday", "duration_days": 2, "budget_amount": 10000, "budget_currency": "TRY"}}
    """
    response = get_llm().invoke(fallback_prompt)
    content = response.content.strip()
    parsed_dict = json.loads(content)

    # Yedek çözümde de para birimi standartlaştırmasını yapıyoruz
    if parsed_dict.get("budget_currency"):
            currency_lower = parsed_dict["budget_currency"].lower()
            if currency_lower in ["tl", "lira", "türk lirası"]:
                parsed_dict["budget_currency"] = "TRY"
            elif currency_lower in ["euro", "eur", "€"]:
                parsed_dict["budget_currency"] = "EUR"
            elif currency_lower in ["dolar", "usd", "$"]:
                parsed_dict["budget_currency"] = "USD"
            elif currency_lower in ["sterlin", "pound", "gbp", "£"]:
                parsed_dict["budget_currency"] = "GBP"
            else:
                parsed_dict["budget_currency"] = parsed_dict["budget_currency"].upper()
    elif parsed_dict.get("budget_amount") is not None:
            parsed_dict["budget_currency"] = "TRY"

    return parsed_dict