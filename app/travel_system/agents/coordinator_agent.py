# app/travel_system/agents/coordinator_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ConversationBufferMemory # Kaldırıldı
# parse_travel_query import'u kaldırıldı, koordinatör kullanmıyor.
# from ..tools.parsing_tools import parse_travel_query
from app.core.llm import get_llm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Sistem mesajı (güncellendi)
TRAVEL_COORDINATOR_SYSTEM_MESSAGE = """You are the Travel Coordinator Agent. You are responsible for compiling information from other agents into a final, user-friendly travel plan in Turkish.

You receive summaries for:
- Date and Budget
- Destination Information (including City Info, Weather, Hotel Booking Links, and Map View URL) # <-- İÇERİK GÜNCELLENDİ (Hotel Booking Links)

Your Task:
Synthesize ALL provided information into a fluent and readable TURKISH travel plan. Use the following EXACT headings:
1. Seyahat Özeti
2. Bütçe ve Kur Bilgisi
3. Hava Durumu ve Kıyafet Önerileri
4. Gezilecek Yerler
5. Konaklama Önerileri
6. Harita Görünümü

Important:
- Your response MUST be ONLY the final TURKISH plan under these headings.
- Extract the relevant information for each heading from the provided summaries.
- Under heading 5 ('Konaklama Önerileri'), list the hotel booking site links provided in the Destination Summary. Do not invent hotel details. # <-- TALİMAT GÜNCELLENDİ
- CRITICAL: Ensure the Map View URL (or error message about the map) from the Destination Summary is included under the 'Harita Görünümü' heading.
- If any information is missing or indicates an error (like missing links), note this politely in the relevant section.
- You should NOT call any tools yourself. You only compile the provided text summaries.
"""

def create_coordinator_agent() -> AgentExecutor:
    """Creates the Coordinator Agent Executor without memory."""
    logging.debug("Coordinator Agent oluşturuluyor (hafızasız)...")

    coordinator_prompt = ChatPromptTemplate.from_messages([
        ("system", TRAVEL_COORDINATOR_SYSTEM_MESSAGE),
        # MessagesPlaceholder(variable_name="history"), # <-- KALDIRILDI
        ("human", "{input}"), # Input hala gerekli (compile node'dan gelen prompt)
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Koordinatör araç kullanmıyor
    coordinator_tools = []

    llm_instance = get_llm(temperature=0.1) # Derleme için biraz daha deterministik
    if not llm_instance:
         logging.error("Coordinator Agent için LLM oluşturulamadı!")
         raise ValueError("LLM could not be initialized for Coordinator Agent.")

    coordinator_agent = create_openai_tools_agent(
        llm=llm_instance,
        tools=coordinator_tools, # Boş liste
        prompt=coordinator_prompt
    )

    coordinator_executor = AgentExecutor.from_agent_and_tools(
        agent=coordinator_agent,
        tools=coordinator_tools,
        verbose=True,
        # memory=coordinator_memory, # <-- KALDIRILDI
        handle_parsing_errors=True
    )

    logging.debug("Coordinator Agent başarıyla oluşturuldu (hafızasız).")
    return coordinator_executor