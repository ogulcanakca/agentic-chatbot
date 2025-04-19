# agents/destination_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from ..tools.destination_tools import search_city_info, get_weather_forecast, Google_Hotels_with_tavily
from app.core.llm import get_llm

# Şehir hakkında genel bilgi ve hava durumu bilgisini toplayan agent için sistem mesajını tanımlıyoruz
DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE = """You are the Destination Research Agent, responsible for gathering and analyzing information about travel destinations.
Your specific duties include:

1. Researching city information including attractions, culture, and local customs using `search_city_info`.
2. Finding suitable accommodation options within the traveler's budget and dates using `Google_Hotels_with_tavily`.
3. Checking weather forecasts using `get_weather_forecast` and providing appropriate clothing recommendations based on its output.

Important:
- Focus on the most relevant and reliable information.
- Prioritize practical insights that will help the traveler.
- Consider the specific travel dates provided when making recommendations.
- Combine the findings from the tools into a comprehensive Turkish summary covering city info, weather/clothing, and accommodation.
- Communicate in Turkish when presenting your findings.
"""

# Agent'ı oluşturan fonksiyonu tanımlıyoruz
def create_destination_agent():
    # Agent'ın kullanacağı prompt template'ini hazırlıyoruz
    destination_prompt = ChatPromptTemplate.from_messages([
        ("system", DESTINATION_RESEARCH_AGENT_SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Konuşma geçmişini tutmak için hafıza modülünü oluşturuyoruz
    destination_memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # Agent'ın kullanabileceği tool'ları tanımlıyoruz
    destination_tools = [search_city_info, get_weather_forecast, Google_Hotels_with_tavily]
    destination_agent = create_openai_tools_agent(
        llm=get_llm(),
        tools=destination_tools,
        prompt=destination_prompt
    )

    # Agent'ın tool'larla birlikte çalışacağı executor nesnesini oluşturuyoruz
    destination_executor = AgentExecutor.from_agent_and_tools(
        agent=destination_agent,
        tools=destination_tools,
        verbose=True,
        memory=destination_memory
    )
    
    return destination_executor