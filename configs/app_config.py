# configs/app_config.py

from pathlib import Path
import sys
import logging
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredFileLoader
)

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Config for app/storage/database.py

# Embedding model used
MODEL_NAME = "intfloat/multilingual-e5-large"

# Data path for ChromaDB
CHROMA_DATA_PATH = str(project_root / "data" / "embeddings")

def create_chroma_data_path():
    Path(CHROMA_DATA_PATH).mkdir(parents=True, exist_ok=True)
    logging.info(f"ChromaDB data path: {CHROMA_DATA_PATH}")

# Config for app/graph.py

# Node that classifies the query
NODE_SUPERVISOR = "supervisor"
# Resmi Gazete RAG agent
NODE_RESMI_GAZETE = "resmi_gazete_agent"
# News / General Information agent (ReAct)
NODE_NEWS = "news_agent"
# Agent for cases where no help can be provided
NODE_FALLBACK = "fallback_agent"

NODE_TRAVEL = "travel_agent"
NODE_AGENTIC_RAG = "agentic_rag_agent"
BELGE_SORUSU_CATEGORY = "Document Question"

# app/agents/agentic_rag_agent.py
LOADER_MAPPING = {
    ".pdf": PyPDFLoader, 
    ".txt": TextLoader, 
    ".md": TextLoader, 
    ".docx": Docx2txtLoader
}

# app/travel_system/tools/budget_tools.py
CITY_CURRENCY_MAP = {
    "paris": "EUR", "kyoto": "JPY", "london": "GBP", "new york": "USD",
    "istanbul": "TRY", "ankara": "TRY", "izmir": "TRY",
}
