# app/travel_system/agents/destination_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ConversationBufferMemory # Kaldırıldı

# Araçları import et (güncellenmiş haliyle)
from ..tools.destination_tools import (
    search_city_info,
    get_weather_forecast,
    search_hotel_booking_links, # <-- DEĞİŞTİ
    get_tomtom_map_url
)
from app.core.llm import get_llm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Sistem mesajı (güncellendi)
DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE = """You are the Destination Research Agent. Your goal is to gather travel information and present it clearly in Turkish.

**Your Tasks:**
1.  Use `search_city_info` for the DESTINATION city.
2.  Use `get_weather_forecast` for the DESTINATION city and dates.
3.  Use `search_hotel_booking_links` for the DESTINATION city and dates to find relevant booking site URLs. # <-- GÖREV GÜNCELLENDİ
4.  Use `get_tomtom_map_url` with `city_name`=DESTINATION to get a map URL.

**Output Requirements:**
- Combine results into a single, comprehensive response in Turkish.
- Structure with EXACT Turkish headings: 'Şehir Bilgileri', 'Hava Durumu/Kıyafet Önerileri', 'Otel Seçenekleri', 'Harita Görünümü'.
- Under 'Otel Seçenekleri', list the booking site links found by the tool. Do not claim to provide specific hotel details. # <-- ÇIKTI GEREKSİNİMİ GÜNCELLENDİ
- CRITICAL: Include map tool output under 'Harita Görünümü'. If error, state it.
- Respond ONLY in Turkish. Do not include thoughts. If a tool fails, note it politely and continue.
"""

def create_destination_agent() -> AgentExecutor:
    """Creates the Destination Research Agent Executor without memory."""
    logging.debug("Destination Agent oluşturuluyor (hafızasız)...")

    destination_prompt = ChatPromptTemplate.from_messages([
        ("system", DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE),
        # MessagesPlaceholder(variable_name="history"), # <-- KALDIRILDI
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Kullanılacak araçlar (güncellendi)
    destination_tools = [
        search_city_info,
        get_weather_forecast,
        search_hotel_booking_links, # <-- DEĞİŞTİ
        get_tomtom_map_url
    ]
    logging.debug(f"Destination Agent için araçlar: {[tool.name for tool in destination_tools]}")

    llm_instance = get_llm()
    if not llm_instance:
        logging.error("Destination Agent için LLM oluşturulamadı!")
        raise ValueError("LLM could not be initialized for Destination Agent.")

    destination_agent_runnable = create_openai_tools_agent(
        llm=llm_instance,
        tools=destination_tools,
        prompt=destination_prompt
    )

    destination_executor = AgentExecutor.from_agent_and_tools(
        agent=destination_agent_runnable,
        tools=destination_tools,
        verbose=True,
        # memory=destination_memory, # <-- KALDIRILDI
        handle_parsing_errors=True,
        # max_iterations=5
    )

    logging.debug("Destination Agent başarıyla oluşturuldu (hafızasız).")
    return destination_executor