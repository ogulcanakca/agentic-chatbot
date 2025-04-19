# agents/coordinator_agent.py

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from ..tools.parsing_tools import parse_travel_query
from app.core.llm import get_llm
# Seyahat koordinatörü agent'ı için sistem mesajını tanımlıyoruz
TRAVEL_COORDINATOR_SYSTEM_MESSAGE = """You are the Travel Coordinator Agent, responsible for managing the entire travel planning process.
Your job is to understand the user's travel request, delegate specific tasks to specialized agents, and compile their findings into a comprehensive travel plan.

You should:
1. Parse the user's initial travel query to extract key information using the parse_travel_query tool. Return the result clearly.
2. Coordinate with specialized agents for detailed information.
3. Compile all information into a clear, organized travel plan for the user.
4. Communicate directly with the user in Turkish.

Important:
- Always respond in Turkish.
- Be concise but comprehensive.
- Make sure to capture all necessary travel details.
- Delegate specific tasks rather than attempting to do everything yourself.
"""

# Koordinatör agent'ı oluşturan fonksiyonu tanımlıyoruz
def create_coordinator_agent():
    
    # Agent'ın kullanacağı prompt template'ini hazırlıyoruz
    coordinator_prompt = ChatPromptTemplate.from_messages([
        ("system", TRAVEL_COORDINATOR_SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Konuşma geçmişini tutmak için hafıza modülünü oluşturuyoruz
    coordinator_memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # Agent'ın kullanabileceği tool'ları tanımlıyoruz
    coordinator_tools = [parse_travel_query] 
    coordinator_agent = create_openai_tools_agent(
        llm=get_llm(),
        tools=coordinator_tools,
        prompt=coordinator_prompt
    )
    
    # Agent'ın tool'larla birlikte çalışacağı executor nesnesini oluşturuyoruz
    coordinator_executor = AgentExecutor.from_agent_and_tools(
        agent=coordinator_agent,
        tools=coordinator_tools,
        verbose=True,
        memory=coordinator_memory
    )
    
    return coordinator_executor