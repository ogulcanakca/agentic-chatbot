# app/travel_system/agents/coordinator_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ConversationBufferMemory # Kaldırıldı
from ..tools.parsing_tools import parse_travel_query # Bu araç hala gerekli olabilir mi? (CompileNode prompt'una bağlı)
from app.core.llm import get_llm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# Sistem mesajı aynı kalabilir (history beklemiyor)
TRAVEL_COORDINATOR_SYSTEM_MESSAGE = """Siz Seyahat Koordinatörü Ajanısınız. Diğer ajanlardan gelen bilgileri derleyerek nihai, kullanıcı dostu bir seyahat planını Türkçe olarak sunmakla sorumlusunuz.

Şu konular için özetleri alırsınız:
- Tarih ve Bütçe
- Destinasyon Bilgileri (Şehir Bilgileri, Hava Durumu, Oteller ve Harita Görünümü URL'si dahil)

Göreviniz:
TÜM sağlanan bilgileri akıcı ve okunabilir bir TÜRKÇE seyahat planında birleştirin. Aşağıdaki TAM başlıkları kullanın:
1. Seyahat Özeti
2. Bütçe ve Kur Bilgisi
3. Hava Durumu ve Kıyafet Önerileri
4. Gezilecek Yerler
5. Konaklama Önerileri
6. Harita Görünümü

Önemli:
- Yanıtınız SADECE bu başlıklar altında nihai TÜRKÇE plan olmalıdır.
- Her başlık için ilgili bilgileri sağlanan özetlerden çıkarın.
- ÇOK ÖNEMLİ: Destinasyon Özetinden gelen Harita Görünümü URL'sinin (veya harita hakkında hata mesajının) 'Harita Görünümü' başlığı altında dahil edildiğinden emin olun.
- Herhangi bir bilgi eksikse veya hata gösteriyorsa, ilgili bölümde bunu nazikçe belirtin.
- Kendiniz herhangi bir tool çağırmamalısınız. Sadece sağlanan metin özetlerini derlemelisiniz.
"""

def create_coordinator_agent() -> AgentExecutor:
    """Creates the Coordinator Agent Executor without memory."""
    logging.debug("Coordinator Agent oluşturuluyor (hafızasız)...")
    
    # Prompt template'inden history placeholder'ını kaldır
    coordinator_prompt = ChatPromptTemplate.from_messages([
        ("system", TRAVEL_COORDINATOR_SYSTEM_MESSAGE),
        # MessagesPlaceholder(variable_name="history"), # <-- KALDIRILDI
        ("human", "{input}"), # Input hala gerekli (compile node'dan gelen prompt)
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Hafıza modülü oluşturma kaldırıldı
    # coordinator_memory = ConversationBufferMemory(...)

    # Koordinatör normalde araç kullanmıyor (sadece derleme yapıyor)
    coordinator_tools = [] 
    # Eğer prompt'unuz Coordinator'ın parse_travel_query'yi çağırmasını istiyorsa,
    # bu aracı burada bırakmanız gerekir:
    # coordinator_tools = [parse_travel_query] 

    llm_instance = get_llm(temperature=0.1) # Derleme için biraz daha deterministik
    if not llm_instance:
         logging.error("Coordinator Agent için LLM oluşturulamadı!")
         raise ValueError("LLM could not be initialized for Coordinator Agent.")
         
    coordinator_agent = create_openai_tools_agent(
        llm=llm_instance,
        tools=coordinator_tools, # Genellikle boş liste
        prompt=coordinator_prompt
    )
    
    # Executor oluştururken memory argümanını kaldır
    coordinator_executor = AgentExecutor.from_agent_and_tools(
        agent=coordinator_agent,
        tools=coordinator_tools,
        verbose=True,
        # memory=coordinator_memory, # <-- KALDIRILDI
        handle_parsing_errors=True
    )
    
    logging.debug("Coordinator Agent başarıyla oluşturuldu (hafızasız).")
    return coordinator_executor