# app/graph.py
import logging
import sys
from pathlib import Path
from typing import Optional, TypedDict, List # List eklendi (isteğe bağlı)

from langgraph.graph import StateGraph, END

# Proje kök dizinini sys.path'e ekleme
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Agent'ları import et
from app.agents.supervisor import classify_query
from app.agents.resmi_gazete_agent import generate_resmi_gazete_answer
from app.agents.news_agent import handle_news_query
from app.agents.fallback_agent import handle_fallback
from app.agents.travel_agent import handle_travel_query # Yeni agent'ı import et

# Node isimlerini config'den al
from configs.app_config import NODE_SUPERVISOR, NODE_RESMI_GAZETE, NODE_NEWS, NODE_FALLBACK, NODE_TRAVEL # NODE_TRAVEL eklendi

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# State'i güncelle (pdf_path eklendi)
class AgentState(TypedDict):
    query: str
    classification: Optional[str]
    context: Optional[str]
    answer: Optional[str]
    source: Optional[str]
    pdf_path: Optional[str] # Seyahat planı PDF yolu için
    # İsteğe bağlı: Mesaj geçmişi için
    # messages: Optional[List[dict]] 

# Yönlendirme fonksiyonunu güncelle
def route_based_on_classification(state: AgentState) -> str:
    classification_result = state.get("classification")
    logging.info(f"[Router] Sınıflandırma sonucuna göre yönlendirme: '{classification_result}'")

    if classification_result == "Resmi Gazete":
        return NODE_RESMI_GAZETE
    elif classification_result == "News":
        return NODE_NEWS
    elif classification_result == "Travel": # Yeni yönlendirme kuralı
        return NODE_TRAVEL
    # elif classification_result == "Other": # 'Other' için Fallback mantığı devam ediyor
    #     return NODE_FALLBACK
    else: # 'Other' dahil diğer tüm durumlar (None, geçersiz vb.) Fallback'e gitsin
        logging.warning(f"Beklenmedik veya 'Other' sınıflandırma '{classification_result}'. Fallback'e yönlendiriliyor.")
        return NODE_FALLBACK

logging.info("LangGraph iş akışı (workflow) oluşturuluyor...")
workflow = StateGraph(AgentState)

# Düğümleri ekle (yeni travel node dahil)
workflow.add_node(NODE_SUPERVISOR, classify_query)
workflow.add_node(NODE_RESMI_GAZETE, generate_resmi_gazete_answer)
workflow.add_node(NODE_NEWS, handle_news_query)
workflow.add_node(NODE_TRAVEL, handle_travel_query) # Yeni travel node'u ekle
workflow.add_node(NODE_FALLBACK, handle_fallback)
logging.info("Graph'a düğümler eklendi: Supervisor, Resmi Gazete, News, Travel, Fallback.")

workflow.set_entry_point(NODE_SUPERVISOR)
logging.info(f"Graph giriş noktası: '{NODE_SUPERVISOR}'")

# Koşullu kenarları güncelle (yeni travel hedefi dahil)
workflow.add_conditional_edges(
    NODE_SUPERVISOR,
    route_based_on_classification,
    {
        NODE_RESMI_GAZETE: NODE_RESMI_GAZETE,
        NODE_NEWS: NODE_NEWS,
        NODE_TRAVEL: NODE_TRAVEL, # Travel için hedef
        NODE_FALLBACK: NODE_FALLBACK # Fallback için hedef (Other ve diğer durumlar)
    }
)
logging.info(f"'{NODE_SUPERVISOR}' sonrası koşullu yönlendirme güncellendi.")

# Tüm agent düğümlerinden END'e kenar ekle
workflow.add_edge(NODE_RESMI_GAZETE, END)
workflow.add_edge(NODE_NEWS, END)
workflow.add_edge(NODE_TRAVEL, END) # Travel agent'ından sonra da bitir
workflow.add_edge(NODE_FALLBACK, END)
logging.info("Alt agent düğümlerinden (Resmi Gazete, News, Travel, Fallback) sonra graph bitiş noktaları (END) eklendi.")

# Graph'ı derle
graph_app = workflow.compile()
logging.info("LangGraph iş akışı başarıyla derlendi ve 'graph_app' olarak hazırlandı.")