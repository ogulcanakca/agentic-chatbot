# app/agents/fallback_agent.py

import logging
from typing import Dict, Any
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.agent_config import FALLBACK_RESPONSE


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


def handle_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    # Hangi sorgu için fallback'e düşüldüğü loglanıyor
    original_query = state.get("query", "belirtilmemiş")
    logging.warning(f"Fallback agent tetiklendi. Kullanıcı sorgusu (ilk 100 karakter): '{original_query[:100]}...'")

    # State'i güncellemek üzere 'answer' anahtarıyla sonucu içeren bir dict döndürülüyor
    return {"answer": FALLBACK_RESPONSE, "source": "Fallback Agent"}
