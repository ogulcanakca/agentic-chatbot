# app/travel_system/tools/budget_tools.py

import os 
import requests
from typing import Optional, Dict, Any 
from langchain_core.tools import tool
import logging
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.app_config import CITY_CURRENCY_MAP

@tool
def get_exchange_rates_and_budget(destination: str, budget_amount: Optional[float] = None, budget_currency: str = "TRY") -> Dict[str, Any]:
    """
    Determine the destination currency for the given destination, basic exchange rates 
    (TRY, EUR, USD to destination currency) and if specified 
    simply assesses the adequacy of the budget. 
    Uses ExchangeRate-API.
    """
    api_key = os.getenv("EXCHANGERATE_API_KEY")
    if not api_key:
        return {"error": "ExchangeRate-API key not found in environment variables."}

    destination_lower = destination.lower()
    target_currency = CITY_CURRENCY_MAP.get(destination_lower)
    
    if not target_currency:
        if "japan" in destination_lower or "tokyo" in destination_lower or "kyoto" in destination_lower:
             target_currency = "JPY"
        elif "america" in destination_lower or "usa" in destination_lower or "new york" in destination_lower:
             target_currency = "USD"
        elif "uk" in destination_lower or "london" in destination_lower:
             target_currency = "GBP"
        elif "euro" in destination_lower or "europe" in destination_lower or "paris" in destination_lower or "berlin" in destination_lower: # Broad assumption
             target_currency = "EUR"
        else:
             return {"error": f"Target currency for '{destination}' could not be determined. It might need to be added to the map."}

    base_currencies = ["TRY", "EUR", "USD"]
    if target_currency in base_currencies:
        base_currencies.remove(target_currency)
        
    rates = {}
    if not base_currencies and target_currency == "TRY":
         rates["TRY"] = 1.0
         rates["EUR"] = None 
         rates["USD"] = None
    elif not base_currencies:
         rates[target_currency] = 1.0

    # As the base can't be changed in the free plan, we'll convert from USD
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"

    try:
        response = requests.get(url)
        response.raise_for_status() 
        data = response.json()

        if data.get("result") == "success":
            usd_rates = data.get("conversion_rates", {})
            
            usd_to_target = usd_rates.get(target_currency)
            if usd_to_target is None:
                 return {"error": f"Could not find exchange rate for target currency '{target_currency}' in the API response."}

            for base in ["TRY", "EUR", "USD"]:
                if base == target_currency:
                     rates[base] = 1.0
                     continue
                
                usd_to_base = usd_rates.get(base)
                if usd_to_base is None:
                     rates[base] = None 
                     logging.warning(f"Could not find exchange rate for {base} from USD in the API response.")
                else:
                     try:
                         rates[base] = usd_to_target / usd_to_base
                     except ZeroDivisionError:
                          rates[base] = None 
                          logging.error(f"Error dividing by zero while calculating exchange rate: Base={base}")

            budget_evaluation = "Not specified"
            if budget_amount is not None:
                if budget_currency == target_currency:
                    converted_budget = budget_amount
                elif budget_currency in rates and rates[budget_currency] is not None:
                    converted_budget = budget_amount * rates[budget_currency]
                else:
                    converted_budget = None
                    budget_evaluation = f"Could not evaluate due to missing exchange rate for {budget_currency}."

                if converted_budget is not None:
                     if converted_budget < 100:
                          budget_evaluation = f"The budget ({converted_budget:.2f} {target_currency}) seems very low."
                     elif converted_budget < 500:
                          budget_evaluation = f"The budget ({converted_budget:.2f} {target_currency}) may be limited."
                     else:
                          budget_evaluation = f"The budget ({converted_budget:.2f} {target_currency}) seems reasonable."
                     
            formatted_rates = {f"1 {cur}": f"{rate:.4f} {target_currency}" if rate is not None else "N/A" for cur, rate in rates.items()}

            return {
                "target_currency": target_currency,
                "rates": formatted_rates,
                "budget_evaluation": budget_evaluation,
                "raw_rates" : rates
            }
        else:
            error_type = data.get("error-type", "Unknown API error")
            logging.error(f"ExchangeRate-API Error: {error_type}")
            return {"error": f"Exchange rate API error: {error_type}"}

    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to the exchange rate API: {e}", exc_info=True)
        return {"error": f"Could not connect to the exchange rate API: {e}"}
    except Exception as e:
        logging.error(f"Unexpected error while fetching exchange rates: {e}", exc_info=True)
        return {"error": f"Error while fetching exchange rates: {e}"}
