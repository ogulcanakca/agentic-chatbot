# configs/app_config.py

from pathlib import Path
import sys
import logging

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))


# app/storage/database.py için config

# Kullanılan embedding modeli
MODEL_NAME = "intfloat/multilingual-e5-large"

# ChromaDB için veri yolu
CHROMA_DATA_PATH = str(project_root / "data" / "embeddings")

def create_chroma_data_path():
    Path(CHROMA_DATA_PATH).mkdir(parents=True, exist_ok=True)
    logging.info(f"ChromaDB veri yolu: {CHROMA_DATA_PATH}")
    
# app/graph.py için config 

# Sorguyu sınıflandıran düğüm
NODE_SUPERVISOR = "supervisor"       
# Resmi Gazete RAG agent'ı   
NODE_RESMI_GAZETE = "resmi_gazete_agent"  
# Haber/Genel Bilgi agent'ı (ReAct)
NODE_NEWS = "news_agent"        
 # Yardımcı olamama durumu için agent
NODE_FALLBACK = "fallback_agent"
         
NODE_TRAVEL = "travel_agent" 
NODE_AGENTIC_RAG = "agentic_rag_agent"