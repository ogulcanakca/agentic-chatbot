# agents/destination_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from ..tools.destination_tools import search_city_info, get_weather_forecast, Google_Hotels_with_tavily, get_tomtom_map_url
from app.core.llm import get_llm
import logging

# Şehir hakkında genel bilgi ve hava durumu bilgisini toplayan agent için sistem mesajını tanımlıyoruz
# app/travel_system/agents/destination_agent.py içinde

DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE = """You are the Destination Research Agent. Your goal is to gather travel information and present it clearly in Turkish.

**Your Tasks:**
1.  Use `search_city_info` for the DESTINATION city to get general info, attractions, etc.
2.  Use `get_weather_forecast` for the DESTINATION city and the specified dates to get the forecast and clothing suggestions.
3.  Use `Google Hotels_with_tavily` for the DESTINATION city and dates (reference budget if available). Summarize findings, noting limitations if specific hotel details aren't available from the search simulation.
4.  Use `get_tomtom_map_url`, providing BOTH `destination_city_name` and (if available) `origin_city_name` to generate a static map URL.

**Output Requirements:**
- Combine the results from ALL FOUR tools into a single, comprehensive response.
- The response MUST be in Turkish.
- The response MUST be structured with the following EXACT Turkish headings:
    - **Şehir Bilgileri** (from `search_city_info`)
    - **Hava Durumu/Kıyafet Önerileri** (from `get_weather_forecast`)
    - **Otel Seçenekleri** (from `Google Hotels_with_tavily`)
    - **Harita Görünümü** (from `get_tomtom_map_url`)
- **CRITICAL:** Under the 'Harita Görünümü' heading, you MUST include the exact URL string returned by the `get_tomtom_map_url` tool. 
- If `get_tomtom_map_url` returns an error string (e.g., starting with 'Hata:'), then under 'Harita Görünümü', state that the map could not be generated and include the error reason provided by the tool.
- Do NOT include your thought process, intermediate steps, or raw tool outputs in the final response. Only provide the structured Turkish summary.
"""

# create_destination_agent fonksiyonunun geri kalanı aynı kalabilir.
# ...

# --- Agent Oluşturma Fonksiyonunu Güncelle ---
def create_destination_agent() -> AgentExecutor: # AgentExecutor döndürdüğünü belirtmek iyi bir pratik
    """Creates the Destination Research Agent with its tools."""
    
    logging.debug("Destination Agent oluşturuluyor...")
    
    # Agent'ın kullanacağı prompt template'ini hazırla (değişiklik yok)
    destination_prompt = ChatPromptTemplate.from_messages([
        ("system", DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="history"), # Hafıza için yer tutucu
        ("human", "{input}"), # Kullanıcı girdisi
        MessagesPlaceholder(variable_name="agent_scratchpad"), # Agent'ın çalışma alanı
    ])

    # Konuşma geçmişini tutmak için hafıza modülü (değişiklik yok)
    destination_memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # Agent'ın kullanabileceği tool'ları tanımla (yeni araç eklendi)
    destination_tools = [
        search_city_info, 
        get_weather_forecast, 
        Google_Hotels_with_tavily,
        get_tomtom_map_url  # <-- Yeni harita aracını listeye ekle
    ]
    logging.debug(f"Destination Agent için araçlar: {[tool.name for tool in destination_tools]}")

    # LLM örneğini al
    llm_instance = get_llm() # Gerekirse parametre (örn. temperature) eklenebilir
    if not llm_instance:
        logging.error("Destination Agent için LLM örneği oluşturulamadı!")
        # Hata durumunda ne yapılacağına karar verilmeli, şimdilik None döndürelim veya hata fırlatalım
        raise ValueError("Destination Agent LLM could not be initialized.")

    # OpenAI Tools Agent'ını oluştur (değişiklik yok)
    destination_agent_runnable = create_openai_tools_agent(
        llm=llm_instance,
        tools=destination_tools,
        prompt=destination_prompt
    )

    # Agent'ın tool'larla birlikte çalışacağı executor nesnesini oluştur (değişiklik yok)
    destination_executor = AgentExecutor.from_agent_and_tools(
        agent=destination_agent_runnable,
        tools=destination_tools,
        verbose=True, # Geliştirme sırasında logları görmek için True
        memory=destination_memory,
        # Hataları daha iyi yakalamak için (isteğe bağlı)
        handle_parsing_errors=True, 
        # max_iterations=5 # Sonsuz döngüleri engellemek için (isteğe bağlı)
    )
    
    logging.debug("Destination Agent başarıyla oluşturuldu.")
    return destination_executor