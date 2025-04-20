# app/graph.py

import logging
import sys
from pathlib import Path
from typing import Optional, List # TypedDict ve bytes artık state.py'de

from langgraph.graph import StateGraph, END

# Proje kök dizini
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Agent'ları import et (Aynı kalıyor)
from app.agents.supervisor import classify_query
from app.agents.resmi_gazete_agent import generate_resmi_gazete_answer
from app.agents.news_agent import handle_news_query
from app.agents.fallback_agent import handle_fallback
from app.agents.travel_agent import handle_travel_query
from app.agents.agentic_rag_agent import handle_uploaded_doc_query

# State import'u state.py'den (Aynı kalıyor)
from app.core.state import AgentState

# Node isimleri config'den (Aynı kalıyor)
from configs.app_config import (
    NODE_SUPERVISOR, NODE_RESMI_GAZETE, NODE_NEWS,
    NODE_FALLBACK, NODE_TRAVEL, NODE_AGENTIC_RAG
)
# Yeni kategori adını doğrudan string olarak kullanacağız
BELGE_SORUSU_CATEGORY = "Belge Sorusu" # Config'e eklediğiniz isimle aynı olmalı

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Yönlendirme fonksiyonunu güncelle
def route_based_on_classification(state: AgentState) -> str:
    # Doğrudan yönlendirme kontrolü (Aynı kalıyor)
    if state.get("route_directly_to_agentic_rag"):
        logging.info(f"[Router] Doğrudan yönlendirme işareti algılandı. Yönlendirme: '{NODE_AGENTIC_RAG}'")
        return NODE_AGENTIC_RAG

    # Sınıflandırma sonucu (Aynı kalıyor)
    classification_result = state.get("classification")
    logging.info(f"[Router] Sınıflandırma sonucuna göre yönlendirme: '{classification_result}'")

    # Mevcut yönlendirmeler (Aynı kalıyor)
    if classification_result == "Resmi Gazete":
        return NODE_RESMI_GAZETE
    elif classification_result == "News":
        return NODE_NEWS
    elif classification_result == "Travel":
        return NODE_TRAVEL
    # --- YENİ KATEGORİ KONTROLÜ ---
    elif classification_result == BELGE_SORUSU_CATEGORY:
        logging.info(f"[Router] Sınıflandırma '{BELGE_SORUSU_CATEGORY}'. Yönlendirme: '{NODE_AGENTIC_RAG}'")
        return NODE_AGENTIC_RAG
    # ----------------------------
    else: # Fallback (Aynı kalıyor)
        logging.warning(f"Beklenmedik veya 'Other' sınıflandırma '{classification_result}'. Fallback'e yönlendiriliyor.")
        return NODE_FALLBACK

# --- Workflow Tanımlama ve Düğüm Ekleme (Aynı kalıyor) ---
logging.info("LangGraph iş akışı (workflow) oluşturuluyor...")
workflow = StateGraph(AgentState)

workflow.add_node(NODE_SUPERVISOR, classify_query)
workflow.add_node(NODE_RESMI_GAZETE, generate_resmi_gazete_answer)
workflow.add_node(NODE_NEWS, handle_news_query)
workflow.add_node(NODE_TRAVEL, handle_travel_query)
workflow.add_node(NODE_FALLBACK, handle_fallback)
workflow.add_node(NODE_AGENTIC_RAG, handle_uploaded_doc_query) # Bu zaten doğru fonksiyonu gösteriyor
logging.info(f"Graph'a düğümler eklendi.")

# --- Giriş Noktası (Aynı kalıyor) ---
workflow.set_entry_point(NODE_SUPERVISOR)
logging.info(f"Graph giriş noktası: '{NODE_SUPERVISOR}'")

# --- Koşullu Kenarları Güncelle ---
workflow.add_conditional_edges(
    NODE_SUPERVISOR,
    route_based_on_classification,
    {
        NODE_RESMI_GAZETE: NODE_RESMI_GAZETE,
        NODE_NEWS: NODE_NEWS,
        NODE_TRAVEL: NODE_TRAVEL,
        NODE_FALLBACK: NODE_FALLBACK,
        NODE_AGENTIC_RAG: NODE_AGENTIC_RAG, # Doğrudan yönlendirme için hedef
        BELGE_SORUSU_CATEGORY: NODE_AGENTIC_RAG # Yeni kategori için hedef
    }
)
logging.info(f"'{NODE_SUPERVISOR}' sonrası koşullu yönlendirme güncellendi ('{BELGE_SORUSU_CATEGORY}' hedefi eklendi).")

# --- Bitiş Kenarları (Aynı kalıyor) ---
workflow.add_edge(NODE_RESMI_GAZETE, END)
workflow.add_edge(NODE_NEWS, END)
workflow.add_edge(NODE_TRAVEL, END)
workflow.add_edge(NODE_FALLBACK, END)
workflow.add_edge(NODE_AGENTIC_RAG, END)
logging.info("Alt agent düğümlerinden sonra graph bitiş noktaları (END) eklendi.")

# --- Graph Derleme (Aynı kalıyor) ---
graph_app = workflow.compile()
logging.info("LangGraph iş akışı başarıyla derlendi ve 'graph_app' olarak hazırlandı.")