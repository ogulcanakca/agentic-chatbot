# app/agents/news_agent.py

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain_core.prompts import PromptTemplate

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.agent_config import LANGCHAIN_HUB_AVAILABLE, REACT_HUB_PROMPT_PATH, MANUAL_REACT_PROMPT_TEMPLATE

from app.tools.external_apis import wikipedia_tool, web_search_tool
from app.core.llm import get_llm


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

NEWS_AGENT_TOOLS = [wikipedia_tool, web_search_tool]

# Agent Executor'ı her seferinde oluşturmak yerine cache'liyoruz
agent_executor: Optional[AgentExecutor] = None

# Agent Executor'ı almak veya oluşturmak için kullanılan fonksiyon
def get_news_agent_executor() -> Optional[AgentExecutor]:
    global agent_executor
    if agent_executor:
        logging.debug("Önbellekten News Agent Executor döndürülüyor.")
        return agent_executor

    logging.info("Yeni News Agent Executor oluşturuluyor...")
    try:
        llm = get_llm(temperature=0.7)

        tools = NEWS_AGENT_TOOLS

        prompt = None
        
        # Eğer Langchain Hub kullanılabiliyorsa, ReAct prompt'u oradan çekilmeye çalışılacak
        # Eğer çekilemezse, manuel olarak oluşturulmuş prompt kullanılacak
        if LANGCHAIN_HUB_AVAILABLE:
            try:
                prompt = hub.pull(REACT_HUB_PROMPT_PATH)
                logging.info(f"Langchain Hub'dan prompt çekildi: {REACT_HUB_PROMPT_PATH}")
            except Exception as e:
                logging.warning(f"Langchain Hub'dan prompt çekilemedi ({e}). Manuel prompt kullanılacak.")
                prompt = None 

        if prompt is None: 
             tool_descriptions = "\n".join([f"{t.name}: {t.description}" for t in tools])
             tool_names = ", ".join([t.name for t in tools])
             prompt = PromptTemplate.from_template(MANUAL_REACT_PROMPT_TEMPLATE).partial(
                 tools=tool_descriptions,
                 tool_names=tool_names
             )
             logging.info("Manuel ReAct prompt kullanılıyor.")

        # News agent'ı oluşturuyoruz
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,  
            handle_parsing_errors=True,
            max_iterations=6
        )
        logging.info("News Agent Executor başarıyla oluşturuldu.")
        return agent_executor

    except Exception as e:
        logging.error(f"News Agent Executor oluşturulurken hata: {e}", exc_info=True)
        return None

# Agent'ı çalıştırmak için kullanılan fonksiyon
def handle_news_query(state: Dict[str, Any]) -> Dict[str, Any]:
    logging.info("News Agent çalıştırılıyor...")
    query: Optional[str] = state.get("query") # Sorgu state'den alınıyor
    final_answer: str = "Haber veya genel bilgi sorgunuz işlenirken beklenmedik bir sorun oluştu." 
    source_info = "News Agent (Web/Wikipedia)" # Cevap için varsayılan bilgi

    # Eğer sorgu yoksa veya boşsa, hata mesajı döndürülüyor
    if not query:
        logging.error("News Agent: State içinde geçerli bir 'query' bulunamadı.")
        final_answer = "Anlaşılamayan veya eksik bir sorgu aldım."
        source_info += " (Hata: Eksik Sorgu)"
        return {"answer": final_answer, "source": source_info}

    logging.info(f"İşlenecek sorgu: '{query}'")

    agent_executor = get_news_agent_executor()

    logging.info(f"News Agent Executor çalıştırılıyor...")
    
    response = agent_executor.invoke({"input": query})

    # Agent'ın nihai cevabı 'output' anahtarında bulunuyor
    final_answer = response.get("output")
    if not final_answer:
        logging.warning("Agent Executor bir çıktı ('output') üretmedi.")
        final_answer = "İsteğiniz işlendi ancak bir cevap üretilemedi. Lütfen farklı bir şekilde sormayı deneyin."
        source_info += " (Agent Cevap Vermedi)"
    else:
        logging.info("News Agent Executor başarıyla tamamlandı.")
        source_info += " (Agent Başarılı)"

    logging.info(f"News Agent tamamlandı. Cevap (ilk 100 karakter): '{final_answer[:100]}...'")
    return {"answer": final_answer, "source": source_info}
