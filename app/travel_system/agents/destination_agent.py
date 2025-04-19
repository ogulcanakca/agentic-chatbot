# app/travel_system/agents/destination_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ConversationBufferMemory # Kaldırıldı
# Araçları import et (kullandığınız son hale göre)
from ..tools.destination_tools import (
    search_city_info, 
    get_weather_forecast, 
    Google_Hotels_with_tavily, 
    get_tomtom_map_url # Basit harita aracı varsayımı
    # generate_destination_map_with_pois # VEYA POI'li harita aracı
)
from app.core.llm import get_llm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Sistem mesajı (içeriği önemli, history beklemiyor)
DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE = """You are the Destination Research Agent. Your goal is to gather travel information and present it clearly in Turkish.

**Your Tasks:**
1.  Use `search_city_info` for the DESTINATION city.
2.  Use `get_weather_forecast` for the DESTINATION city and dates.
3.  Use `Google Hotels_with_tavily` for the DESTINATION city and dates. Note limitations.
4.  Use `get_tomtom_map_url` with `city_name`=DESTINATION to get a map URL.
    (If using POI map tool: 4. Extract places from task 1 text. Call `generate_destination_map_with_pois` with destination and places text.)

**Output Requirements:**
- Combine results into a single, comprehensive response in Turkish.
- Structure with EXACT Turkish headings: 'Şehir Bilgileri', 'Hava Durumu/Kıyafet Önerileri', 'Otel Seçenekleri', 'Harita Görünümü'.
- CRITICAL: Include map tool output under 'Harita Görünümü'. If error, state it.
- Respond ONLY in Turkish. Do not include thoughts.
"""

def create_destination_agent() -> AgentExecutor:
    """Creates the Destination Research Agent Executor without memory."""
    logging.debug("Destination Agent oluşturuluyor (hafızasız)...")
    
    # Prompt template'inden history placeholder'ını kaldır
    destination_prompt = ChatPromptTemplate.from_messages([
        ("system", DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE),
        # MessagesPlaceholder(variable_name="history"), # <-- KALDIRILDI
        ("human", "{input}"), 
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Hafıza modülü oluşturma kaldırıldı
    # destination_memory = ConversationBufferMemory(...)

    # Kullanılacak araçlar (kullandığınız son hale göre güncelleyin)
    destination_tools = [
        search_city_info, 
        get_weather_forecast, 
        Google_Hotels_with_tavily,
        get_tomtom_map_url # VEYA generate_destination_map_with_pois
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

    # Executor oluştururken memory argümanını kaldır
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