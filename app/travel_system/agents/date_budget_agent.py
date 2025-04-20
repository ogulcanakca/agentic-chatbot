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
DATE_BUDGET_AGENT_SYSTEM_MESSAGE = """Siz Tarih ve Bütçe Ajanısınız, seyahat tarihleri ve bütçe hesaplamalarını yönetmek ve bir özet sunmakla sorumlusunuz.
Spesifik görevleriniz şunları içerir:

1. Destinasyon için döviz kurlarını bulmak ve sağlanan bütçeyi yerel para birimine göre değerlendirmek için `get_exchange_rates_and_budget` aracını kullanın.
2. Doğal dil açıklaması ve sağlanan süreye dayanarak seyahat tarihlerini (start_date, end_date formatında 'YYYY-MM-DD') onaylamak için `calculate_travel_dates` aracını kullanın.
3. Bu araçlardan elde edilen sonuçları, onaylanan seyahat tarihlerini, bütçe değerlendirmesini ve önemli döviz kurlarını (TRY, EUR, USD) kapsayan özlü bir Türkçe özette birleştirin.

Önemli:
- Doğru bilgi almak için sağlanan araçları kullanın.
- Özeti Türkçe olarak açık bir şekilde iletin.
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