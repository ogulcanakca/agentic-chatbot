# app/travel_system/agents/date_budget_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ConversationBufferMemory # Kaldırıldı
from ..tools.date_tools import calculate_travel_dates
from ..tools.budget_tools import get_exchange_rates_and_budget
from app.core.llm import get_llm
import logging # Logging ekleyelim

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Sistem mesajı aynı kalır
DATE_BUDGET_AGENT_SYSTEM_MESSAGE = """You are the Date and Budget Agent, responsible for handling travel dates and budget calculations and providing a summary.
Your specific duties include:

1. Use the `get_exchange_rates_and_budget` tool to find exchange rates for the destination and assess the provided budget against the local currency.
2. Use the `calculate_travel_dates` tool to confirm the travel dates (start_date, end_date in 'YYYY-MM-DD') based on the natural language description and duration provided.
3. Combine the results from these tools into a concise Turkish summary covering the confirmed travel dates, the budget assessment, and key exchange rates (TRY, EUR, USD).

Important:
- Use the tools provided to get accurate information.
- Communicate the summary clearly in Turkish.
"""

def create_date_budget_agent() -> AgentExecutor:
    """Creates the Date and Budget Agent Executor without memory."""
    logging.debug("Date Budget Agent oluşturuluyor (hafızasız)...")
    
    # Prompt template'inden history placeholder'ını kaldır
    date_budget_prompt = ChatPromptTemplate.from_messages([
        ("system", DATE_BUDGET_AGENT_SYSTEM_MESSAGE),
        # MessagesPlaceholder(variable_name="history"), # <-- KALDIRILDI
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Hafıza modülü oluşturma kaldırıldı
    # date_budget_memory = ConversationBufferMemory(...) 

    date_budget_tools = [calculate_travel_dates, get_exchange_rates_and_budget]
    
    llm_instance = get_llm(temperature=0.0) # Düşük sıcaklık
    if not llm_instance:
         logging.error("Date Budget Agent için LLM oluşturulamadı!")
         raise ValueError("LLM could not be initialized for Date Budget Agent.")
         
    date_budget_agent = create_openai_tools_agent(
        llm=llm_instance,
        tools=date_budget_tools,
        prompt=date_budget_prompt
    )
    
    # Executor oluştururken memory argümanını kaldır
    date_budget_executor = AgentExecutor.from_agent_and_tools(
        agent=date_budget_agent,
        tools=date_budget_tools,
        verbose=True,
        # memory=date_budget_memory, # <-- KALDIRILDI
        handle_parsing_errors=True # Hata yönetimi kalsın
    )
    
    logging.debug("Date Budget Agent başarıyla oluşturuldu (hafızasız).")
    return date_budget_executor