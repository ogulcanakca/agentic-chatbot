# app/agents/agentic_rag_agent.py

import logging
import sys
from pathlib import Path

from langgraph.graph import StateGraph, END

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.agents.supervisor import classify_query
from app.agents.resmi_gazete_agent import generate_resmi_gazete_answer
from app.agents.news_agent import handle_news_query
from app.agents.fallback_agent import handle_fallback
from app.agents.travel_agent import handle_travel_query
from app.agents.agentic_rag_agent import handle_uploaded_doc_query

from app.core.state import AgentState

from configs.app_config import (
    NODE_SUPERVISOR, NODE_RESMI_GAZETE, NODE_NEWS,
    NODE_FALLBACK, NODE_TRAVEL, NODE_AGENTIC_RAG, BELGE_SORUSU_CATEGORY
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

def route_based_on_classification(state: AgentState) -> str:
    if state.get("route_directly_to_agentic_rag"):
        logging.info(f"[Router] Direct routing flag detected. Routing to: '{NODE_AGENTIC_RAG}'")
        return NODE_AGENTIC_RAG

    classification_result = state.get("classification")
    logging.info(f"[Router] Routing based on classification result: '{classification_result}'")

    if classification_result == "Resmi Gazete":
        return NODE_RESMI_GAZETE
    elif classification_result == "News":
        return NODE_NEWS
    elif classification_result == "Travel":
        return NODE_TRAVEL
    elif classification_result == BELGE_SORUSU_CATEGORY:
        logging.info(f"[Router] Classification '{BELGE_SORUSU_CATEGORY}'. Routing to: '{NODE_AGENTIC_RAG}'")
        return NODE_AGENTIC_RAG
    else: 
        logging.warning(f"Unexpected or 'Other' classification '{classification_result}'. Routing to fallback.")
        return NODE_FALLBACK

logging.info("Creating LangGraph workflow...")
workflow = StateGraph(AgentState)

workflow.add_node(NODE_SUPERVISOR, classify_query)
workflow.add_node(NODE_RESMI_GAZETE, generate_resmi_gazete_answer)
workflow.add_node(NODE_NEWS, handle_news_query)
workflow.add_node(NODE_TRAVEL, handle_travel_query)
workflow.add_node(NODE_FALLBACK, handle_fallback)
workflow.add_node(NODE_AGENTIC_RAG, handle_uploaded_doc_query) 
logging.info(f"Nodes added to the graph.")

workflow.set_entry_point(NODE_SUPERVISOR)
logging.info(f"Graph entry point: '{NODE_SUPERVISOR}'")

workflow.add_conditional_edges(
    NODE_SUPERVISOR,
    route_based_on_classification,
    {
        NODE_RESMI_GAZETE: NODE_RESMI_GAZETE,
        NODE_NEWS: NODE_NEWS,
        NODE_TRAVEL: NODE_TRAVEL,
        NODE_FALLBACK: NODE_FALLBACK,
        NODE_AGENTIC_RAG: NODE_AGENTIC_RAG, 
        BELGE_SORUSU_CATEGORY: NODE_AGENTIC_RAG 
    }
)
logging.info(f"Conditional routing after '{NODE_SUPERVISOR}' updated ('{BELGE_SORUSU_CATEGORY}' target added).")

workflow.add_edge(NODE_RESMI_GAZETE, END)
workflow.add_edge(NODE_NEWS, END)
workflow.add_edge(NODE_TRAVEL, END)
workflow.add_edge(NODE_FALLBACK, END)
workflow.add_edge(NODE_AGENTIC_RAG, END)
logging.info("End points (END) added after sub-agent nodes.")

graph_app = workflow.compile()
logging.info("LangGraph workflow successfully compiled and prepared as 'graph_app'.")
