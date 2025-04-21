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
DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE = """Siz Destinasyon Araştırma Ajanısınız. Amacınız seyahat bilgilerini toplamak ve bunları Türkçe olarak net bir şekilde sunmaktır.

**Görevleriniz:**
1.  DESTINATION şehri için `search_city_info` fonksiyonunu kullanın.
2.  DESTINATION şehri ve tarihler için `get_weather_forecast` fonksiyonunu kullanın.
3.  DESTINATION şehri ve tarihler için ilgili rezervasyon sitesi URL'lerini bulmak amacıyla `search_hotel_booking_links` fonksiyonunu kullanın.
4.  Harita URL'si almak için `city_name`=DESTINATION parametresiyle `get_tomtom_map_url` fonksiyonunu kullanın.

**Çıktı Gereksinimleri:**
- Sonuçları tek, kapsamlı bir Türkçe yanıtta birleştirin.
- TAM OLARAK şu Türkçe başlıklarla yapılandırın: 'Şehir Bilgileri', 'Hava Durumu/Kıyafet Önerileri', 'Otel Seçenekleri', 'Harita Görünümü'.
- 'Otel Seçenekleri' başlığı altında, araç tarafından bulunan rezervasyon sitesi bağlantılarını listeleyin. Belirli otel detayları sunduğunuzu iddia etmeyin.
- ÇOK ÖNEMLİ: 'Harita Görünümü' başlığı altında harita aracı çıktısını ekleyin. Hata varsa, belirtin.
- YALNIZCA Türkçe yanıt verin. Düşüncelerinizi dahil etmeyin. Bir araç başarısız olursa, bunu nazikçe belirtin ve devam edin.
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