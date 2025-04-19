# tools/date_tools.py

from datetime import datetime, timedelta
import dateparser
from langchain_core.tools import tool
from app.core.llm import get_llm

# Bu tool, doğal dil ile girilen tarih ve kalış süresine göre seyahat tarihlerini hesaplar
@tool
def calculate_travel_dates(natural_language_date: str, duration_days: int = 1) -> dict:
    """
    Calculates the start and end dates for travel based on a natural language query
    like 'next Wednesday' or 'in 3 weeks' and the duration of the stay.
    Returns a dictionary with 'start_date' and 'end_date' in 'YYYY-MM-DD' format.
    Uses the current date as a reference.
    """
    
    # Bugünün tarihini al
    today = datetime.now().date()

    # Doğal dil tarif ile tarihi anlamaya çalışıyoruz dateparser kütüphane yardımıyla (Türkçe ve İngilizce desteklenir)
    start_date_obj = dateparser.parse(natural_language_date, languages=['tr', 'en'], settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()})

   # Eğer dateparser tarih çözemezse, LLM ile tarihi belirlemeye çalışıyoruz
    if not start_date_obj:
        prompt = f"""
        Current date is {today.strftime('%Y-%m-%d')}.
        The user wants to start a trip described by the phrase: '{natural_language_date}'.
        What is the exact start date for this trip in 'YYYY-MM-DD' format?
        Only output the date string.
        """
        response = get_llm().invoke(prompt)
        start_date_str = response.content.strip()
        try:
            # LLM'den gelen tarih formatını ayrıştırıyoruz
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
                return {"error": f"Invalid date format received from LLM: {start_date_str}"}
 
    # Başlangıç tarihini alıyoruz
    start_date = start_date_obj.date()
    
    # Kalış süresine göre bitiş tarihini hesaplıyoruz (kalış süresinin kendisi dahil)
    end_date = start_date + timedelta(days=duration_days -1)

    # Hesaplanan tarihleri formatlar ve döner
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
        }