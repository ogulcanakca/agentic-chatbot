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

class TravelQuery(BaseModel):
    origin: Optional[str] = Field(None, description="The starting city or location of the trip, if specified. Defaults to null if not mentioned.")
    destination: str = Field(..., description="The city or place the user wants to travel to.")
    natural_language_date: str = Field(..., description="The user's description of the travel start date (e.g., 'next Wednesday', 'tomorrow', 'in 2 weeks', 'beginning of next month').")
    duration_days: int = Field(..., description="The duration of the stay in days. Extract the number from phrases like '3 days', 'for 5 days', 'one week (7 days)'.")
    budget_amount: Optional[float] = Field(None, description="The user's approximate budget amount, if mentioned.")
    budget_currency: Optional[str] = Field(None, description="The currency of the user's budget (e.g., TRY, EUR, USD, TL, lira), if mentioned. Defaults to null if not recognized.")
    error: Optional[str] = Field(None, description="Error message if parsing fails or required info is missing.")

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
        logging.error("Could not get LLM instance for parsing!")
        return {"error": "Query parsing service is currently unavailable."}

    structured_llm = llm_instance.with_structured_output(TravelQuery)

    today_date_str = datetime.now().date().strftime('%Y-%m-%d')

    prompt = f"""
    Analyze the following user query and extract travel details according to the TravelQuery schema.
    User Query: "{user_query}"

    Today's date is {today_date_str}. Use this for relative date context, but extract the user's original expression for 'natural_language_date'.

    **Extraction Instructions:**
    - **origin:** Extract the starting city if specified (e.g., 'from Istanbul', 'from Ankara', 'leaving from Izmir...'). If not explicitly mentioned, leave the origin field as null.
    - **destination:** Extract the destination city.
    - **natural_language_date:** Extract the user's description of the start date.
    - **duration_days:** Extract the duration specifically as an integer number of days.
        - 'one week' means 7.
        - '3 days' or 'for 3 days' or 'staying for 3 days' means 3.
        - '5 days' means 5.
        Pay particular attention to numbers associated with 'days' or 'weeks'.
    - **budget_amount:** Extract the numerical budget amount.
    - **budget_currency:** Extract the currency. Normalize common names/symbols ('TL', 'lira', '€', '$', 'Pound', 'Sterling', etc.) to 3-letter ISO codes (TRY, EUR, USD, GBP). If ambiguous or not specified, leave the budget_currency field as null.
    - **error:** If required fields (destination, date, duration) are missing or ambiguous, put an explanatory error message in this field, but still try to extract the other fields.

    **Output Format:** Output only the JSON object conforming to the TravelQuery schema. Do not add any other text.
    """ 

    logging.info(f"Parsing query with LLM: '{user_query}'")
    parsed_dict = None
    try:
        result = structured_llm.invoke(prompt)
        parsed_dict = result.model_dump(exclude_unset=True)
        logging.info(f"Structured parsing successful: {parsed_dict}")

    except Exception as e:
        logging.warning(f"Structured parsing failed: {e}. Trying fallback.", exc_info=True)

        fallback_prompt = f"""
        Analyze the following user query and extract these details: origin, destination, natural_language_date, duration_days, budget_amount, budget_currency.
        Extract the origin city if specified (e.g., 'from Istanbul'). If not specified, set the origin value to null.
        For duration_days, extract the number of days as an integer (e.g., '3 days' -> 3, 'one week' -> 7).
        Normalize currency: 'TL', 'lira' -> 'TRY'; 'Euro', '€' -> 'EUR'; 'Dollar', '$' -> 'USD'; 'Sterling', '£' -> 'GBP'. If currency is ambiguous or missing, set budget_currency value to null.
        Output the result as ONLY a JSON object, without any surrounding text or markdown. Make sure keys are in double quotes.
        User Query: "{user_query}"
        Example Output: {{"origin": "Istanbul", "destination": "Paris", "natural_language_date": "next Wednesday", "duration_days": 7, "budget_amount": 1500, "budget_currency": "EUR"}}
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
            return {"error": f"Query could not be parsed: {fallback_e}"}

    if parsed_dict:
        raw_currency = parsed_dict.get("budget_currency")
        normalized_currency = None
        if raw_currency and isinstance(raw_currency, str):
            currency_lower = raw_currency.lower()
            if currency_lower in ["tl", "lira", "turkish lira", "try"]:
                normalized_currency = "TRY"
            elif currency_lower in ["euro", "eur", "€"]:
                normalized_currency = "EUR"
            elif currency_lower in ["dollar", "usd", "$"]:
                normalized_currency = "USD"
            elif currency_lower in ["sterling", "pound", "gbp", "£"]:
                normalized_currency = "GBP"
            elif len(raw_currency) == 3:
                 normalized_currency = raw_currency.upper()

        if parsed_dict.get("budget_amount") is not None and normalized_currency is None:
             normalized_currency = "TRY"

        if normalized_currency:
            parsed_dict["budget_currency"] = normalized_currency
        elif "budget_currency" in parsed_dict:
             del parsed_dict["budget_currency"]

        if "origin" not in parsed_dict or not parsed_dict.get("origin"):
            default_origin = "Ayrancılar, İzmir" 
            parsed_dict["origin"] = default_origin
            logging.info(f"Origin not specified or empty in query, set to default '{default_origin}'.")

        required_fields = ["destination", "natural_language_date", "duration_days"]
        missing_fields = [field for field in required_fields if field not in parsed_dict or not parsed_dict.get(field)]
        if missing_fields:
            error_msg = parsed_dict.get("error", f"Missing information: {', '.join(missing_fields)} not specified or could not be understood.")
            parsed_dict["error"] = error_msg
            logging.warning(f"Missing fields after parsing: {missing_fields}")

        if "duration_days" not in parsed_dict or not isinstance(parsed_dict.get("duration_days"), int) or parsed_dict.get("duration_days", 0) <= 0:
             logging.error(f"Invalid or zero 'duration_days' parsed: {parsed_dict.get('duration_days')}. Query: '{user_query}'")

        return parsed_dict
    else:
        return {"error": "Query parsing failed (empty result)."}