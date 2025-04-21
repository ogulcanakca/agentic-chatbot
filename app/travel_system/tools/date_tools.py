# tools/date_tools.py

from datetime import datetime, timedelta
import dateparser
from langchain_core.tools import tool
from app.core.llm import get_llm

# This tool calculates the travel dates based on the natural language input for the start date and duration
@tool
def calculate_travel_dates(natural_language_date: str, duration_days: int = 1) -> dict:
    """
    Calculates the start and end dates for travel based on a natural language query
    like 'next Wednesday' or 'in 3 weeks' and the duration of the stay.
    Returns a dictionary with 'start_date' and 'end_date' in 'YYYY-MM-DD' format.
    Uses the current date as a reference.
    """
    today = datetime.now().date()

    start_date_obj = dateparser.parse(natural_language_date, languages=['tr', 'en'], settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()})

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
            # Parsing the date format returned from the LLM
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
                return {"error": f"Invalid date format received from LLM: {start_date_str}"}
 
    # Getting the start date
    start_date = start_date_obj.date()
    
    # Calculating the end date based on the duration (including the duration itself)
    end_date = start_date + timedelta(days=duration_days - 1)

    # Formatting and returning the calculated dates
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
    }
