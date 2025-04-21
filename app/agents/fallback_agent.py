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
    original_query = state.get("query", "not specified")
    logging.warning(f"Fallback agent triggered. User query (first 100 characters): '{original_query[:100]}...'")

    return {"answer": FALLBACK_RESPONSE, "source": "Fallback Agent"}
