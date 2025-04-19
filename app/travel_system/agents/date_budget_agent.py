# agents/date_budget_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from ..tools.date_tools import calculate_travel_dates
from ..tools.budget_tools import get_exchange_rates_and_budget
from app.core.llm import get_llm
# Tarih ve bütçe belirleyen agent için sistem mesajını tanımlıyoruz
DATE_BUDGET_AGENT_SYSTEM_MESSAGE = """You are the Date and Budget Agent, responsible for handling travel dates and budget calculations and providing a summary.
Your specific duties include:

1. Use the `get_exchange_rates_and_budget` tool to find exchange rates for the destination and assess the provided budget against the local currency.
2. Use the `calculate_travel_dates` tool to confirm the travel dates (start_date, end_date in 'YYYY-MM-DD') based on the natural language description and duration provided.
3. Combine the results from these tools into a concise Turkish summary covering the confirmed travel dates, the budget assessment, and key exchange rates (TRY, EUR, USD).

Important:
- Use the tools provided to get accurate information.
- Communicate the summary clearly in Turkish.
"""

# Agent'ı oluşturan fonksiyonu tanımlıyoruz
def create_date_budget_agent():
    # Agent'ın kullanacağı prompt template'ini hazırlıyoruz
    date_budget_prompt = ChatPromptTemplate.from_messages([
        ("system", DATE_BUDGET_AGENT_SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Konuşma geçmişini tutmak için hafıza modülünü oluşturuyoruz
    date_budget_memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # Agent'ın kullanabileceği tool'ları tanımlıyoruz
    date_budget_tools = [calculate_travel_dates, get_exchange_rates_and_budget]
    date_budget_agent = create_openai_tools_agent(
        llm=get_llm(),
        tools=date_budget_tools,
        prompt=date_budget_prompt
    )
    
    # Agent'ın tool'larla birlikte çalışacağı executor nesnesini oluşturuyoruz
    date_budget_executor = AgentExecutor.from_agent_and_tools(
        agent=date_budget_agent,
        tools=date_budget_tools,
        verbose=True,
        memory=date_budget_memory
    )
    
    return date_budget_executor