# app/travel_system/workflow.py
# ASENKRON HALİ (Event loop closed hatası verebilir, ama başlangıç hatası vermemeli)

import json
import logging
from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver # MemorySaver importu gerekli

# Agent'ları ve araçları import et
from .agents.coordinator_agent import create_coordinator_agent
from .agents.date_budget_agent import create_date_budget_agent
from .agents.destination_agent import create_destination_agent 
from .tools.date_tools import calculate_travel_dates      
from .tools.parsing_tools import parse_travel_query # Origin içeren versiyonu varsayıyoruz
# Harita aracını import et (varsa)
# from .tools.destination_tools import get_tomtom_map_url 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# State Tanımı (Origin İLE)
class TravelPlanState(TypedDict):
    user_query: str
    origin: Optional[str] # Origin tekrar eklendi
    parsed_request: Optional[Dict[str, Any]]
    calculated_dates: Optional[Dict[str, str]]
    date_budget_summary: Optional[str]
    destination_summary: Optional[str] 
    final_plan: Optional[str] # 'answer' yerine 'final_plan' kullanıyoruz (orijinal gibi)
    error_message: Optional[str] 

class TravelPlanningSystem:
    def __init__(self):
        logging.info("TravelPlanningSystem başlatılıyor (Async Versiyon)...")
        self.coordinator_agent = create_coordinator_agent()
        self.date_budget_agent = create_date_budget_agent()
        self.destination_agent = create_destination_agent()
        self.app = self.build_graph()
        logging.info("TravelPlanningSystem başarıyla başlatıldı (Async Versiyon).")

    # --- Node Fonksiyonları (ASENKRON) ---

    async def parse_request_node(self, state: TravelPlanState) -> Dict[str, Any]: # async def
        logging.info("[ParseNode] Çalıştırılıyor...")
        user_query = state['user_query']
        try:
            parsed_info = parse_travel_query.func(user_query=user_query) # Origin içeren parser
            logging.info(f"[ParseNode] Ayrıştırma Sonucu: {parsed_info}")
            error_message = parsed_info.get("error")
            required_fields = ["destination", "natural_language_date", "duration_days"]
            missing_fields = [field for field in required_fields if not parsed_info.get(field)] 
            if missing_fields: error_message = parsed_info.get("error", f"Eksik bilgi: {', '.join(missing_fields)}"); logging.warning(f"[ParseNode] Eksik: {missing_fields}")
            return {
                "parsed_request": parsed_info, 
                "origin": parsed_info.get("origin"), # Origin'i state'e ekle
                "error_message": error_message 
            }
        except Exception as e: logging.error(f"[ParseNode] Hata: {e}", exc_info=True); return {"error_message": f"Sorgu ayrıştırılamadı: {e}"}


    async def calculate_dates_node(self, state: TravelPlanState) -> Dict[str, Any]: # async def
        logging.info("[CalculateDatesNode] Çalıştırılıyor...")
        parsed_info = state.get('parsed_request')
        if not parsed_info: logging.warning("[CalculateDatesNode] Bilgi eksik."); return {"error_message": "Cannot calculate dates without parsed info."}
        natural_language_date = parsed_info.get("natural_language_date"); duration_days = parsed_info.get("duration_days")
        if not natural_language_date or duration_days is None: logging.warning("[CalculateDatesNode] Tarih/süre eksik."); return {"error_message": "Missing nl_date or duration."}
        try:
            dates_result = calculate_travel_dates.func(natural_language_date=natural_language_date, duration_days=duration_days)
            logging.info(f"[CalculateDatesNode] Sonuç: {dates_result}")
            if "error" in dates_result: logging.error(f"[CalculateDatesNode] Araç hatası: {dates_result['error']}"); return {"error_message": f"Date calculation failed: {dates_result['error']}"}
            return {"calculated_dates": dates_result, "error_message": None} 
        except Exception as e: logging.error(f"[CalculateDatesNode] Hata: {e}", exc_info=True); return {"error_message": f"Error calculating dates: {e}"}

    async def process_date_budget_node(self, state: TravelPlanState) -> Dict[str, Any]: # async def
        logging.info("[DateBudgetNode] Çalıştırılıyor...")
        parsed_info = state.get('parsed_request'); calculated_dates = state.get('calculated_dates')
        if not parsed_info or not calculated_dates: logging.warning("[DateBudgetNode] Bilgi eksik."); return {"date_budget_summary": "Skipped: Missing info."}
        destination = parsed_info.get('destination'); nl_date = parsed_info.get('natural_language_date'); start_date = calculated_dates.get('start_date'); end_date = calculated_dates.get('end_date'); duration = parsed_info.get('duration_days'); budget_amount = parsed_info.get('budget_amount', 'N/A'); budget_currency = parsed_info.get('budget_currency', '')
        if not all([destination, nl_date, start_date, end_date, duration is not None]): logging.warning("[DateBudgetNode] Alt bilgi eksik."); return {"date_budget_summary": "Skipped: Missing sub-keys."}
        
        date_budget_query = f"""...""" # Prompt içeriği aynı (origin olmadan)
        logging.info("[DateBudgetNode] Date Budget Agent çağrılıyor (ASENKRON)...")
        try:
            agent_input = {"input": date_budget_query}; 
            response = await self.date_budget_agent.ainvoke(agent_input) # await ... ainvoke KULLAN
            logging.info(f"[DateBudgetNode] Agent Ham Yanıtı: {response}")
            summary = response.get("output", "Date/Budget summary error."); logging.info(f"[DateBudgetNode] Agent Özet Sonucu: {summary}")
            error_in_summary = None; # ... (hata kontrolü) ...
            return {"date_budget_summary": summary, "error_message": state.get("error_message") or error_in_summary}
        except Exception as e: logging.error(f"[DateBudgetNode] Hata: {e}", exc_info=True); error_msg = f"Error: {e}"; return {"date_budget_summary": error_msg, "error_message": error_msg}


    async def process_destination_node(self, state: TravelPlanState) -> Dict[str, Any]: # async def
        logging.info("[DestinationNode] Çalıştırılıyor...")
        parsed_info = state.get('parsed_request'); calculated_dates = state.get('calculated_dates')
        origin_city = state.get('origin') # Origin TEKRAR kullanılıyor
        if not parsed_info or not calculated_dates: logging.warning("[DestinationNode] Bilgi eksik."); return {"destination_summary": "Skipped: Missing info."}
        destination_city = parsed_info.get('destination'); start_date = calculated_dates.get('start_date'); end_date = calculated_dates.get('end_date')
        if not all([destination_city, start_date, end_date]): logging.warning("[DestinationNode] Alt bilgi eksik."); return {"destination_summary": "Skipped: Missing sub-keys."}

        # Destination Agent prompt'u (origin İLE, basit harita aracı varsayımıyla)
        destination_query = f"""
        Please collect detailed travel information for the following trip and provide the result as a Turkish summary:
        - Origin: {origin_city or 'Not Specified'} 
        - Destination: {destination_city}
        - Start Date: {start_date}
        - End Date: {end_date}
        - Budget Information (for reference): {parsed_info.get('budget_amount', 'N/A')} {parsed_info.get('budget_currency', '')}

        Tasks & Output Structure (Use EXACT Turkish Headings):
        1. Use `search_city_info` for {destination_city}.
        2. Use `get_weather_forecast` for {destination_city} between {start_date} - {end_date}.
        3. Use `Google Hotels_with_tavily` for {destination_city}. Note limitations.
        4. Use `get_tomtom_map_url` with `city_name`='{destination_city}' (or maybe with origin/dest if tool supports it).
        5. Combine results under: 'Şehir Bilgileri', 'Hava Durumu/Kıyafet Önerileri', 'Otel Seçenekleri', 'Harita Görünümü'. Include map URL. Respond ONLY in Turkish.
        """
        logging.info(f"[DestinationNode] Destination Agent'a gönderilen sorgu/prompt:\n{destination_query}")
        logging.info("[DestinationNode] Destination Agent çağrılıyor (ASENKRON)...")
        try:
            agent_input = {"input": destination_query}; 
            response = await self.destination_agent.ainvoke(agent_input) # await ... ainvoke KULLAN
            logging.info(f"[DestinationNode] Agent Ham Yanıtı: {response}") 
            summary = response.get("output", "Destination summary error."); logging.info(f"[DestinationNode] Agent Özet Sonucu: {summary}") 
            error_in_summary = None; # ... (hata kontrolü) ...
            return {"destination_summary": summary, "error_message": state.get("error_message") or error_in_summary}
        except Exception as e: logging.error(f"[DestinationNode] Hata: {e}", exc_info=True); error_msg = f"Error: {e}"; return {"destination_summary": error_msg, "error_message": error_msg}


    async def compile_final_plan_node(self, state: TravelPlanState) -> Dict[str, Any]: # async def
        logging.info("[CompileNode] Çalıştırılıyor...")
        error_msg = state.get("error_message"); destination_summary = state.get('destination_summary', '?') 
        # ... (Hata kontrolü - origin/destination vs. state'e göre güncellenmeli) ...
        if error_msg and ("parse" in error_msg.lower() or "date calculation failed" in error_msg.lower()):
             logging.error(f"[CompileNode] Kritik hata: {error_msg}"); return {"final_plan": f"Plan oluşturulamadı. Hata: {error_msg}"} 
        elif error_msg: logging.warning(f"Kritik olmayan hata ile devam ediliyor: {error_msg}")

        parsed_info = state.get('parsed_request', {}); calculated_dates = state.get('calculated_dates', {}); start_date = calculated_dates.get('start_date', '?'); end_date = calculated_dates.get('end_date', '?'); date_budget_summary = state.get('date_budget_summary', '?'); destination_summary_for_prompt = destination_summary
        if error_msg: destination_summary_for_prompt = f"(Not: Hedef bilgileri alınırken sorun oluştu: {destination_summary})"
        
        # Coordinator prompt (origin İLE, Harita dahil)
        final_prompt = f"""
        Using the following information, create a final travel plan summary for the user in TURKISH.

        User Request: {state.get('user_query', 'N/A')}
        Parsed Info: {json.dumps(parsed_info, ensure_ascii=False, indent=2)} 
        Dates: {start_date} - {end_date}
        Date/Budget Summary: {date_budget_summary}
        Destination Summary (Includes Map View URL): 
        ```
        {destination_summary_for_prompt}
        ```

        Task: Synthesize ALL info into a TURKISH plan with headings: 
        1. Seyahat Özeti (Origin, Destination, Dates, Duration from Parsed Info)
        2. Bütçe ve Kur Bilgisi 
        3. Hava Durumu ve Kıyafet Önerileri
        4. Gezilecek Yerler 
        5. Konaklama Önerileri
        6. Harita Görünümü (Extract Map URL from Destination Summary)
        If info is missing, state politely. Compile only, do not call tools.
        """
        logging.info(f"[CompileNode] Coordinator Agent'a gönderilen SON PROMPT:\n{final_prompt}")
        logging.info("[CompileNode] Coordinator Agent çağrılıyor (ASENKRON)...")
        try:
            agent_input = {"input": final_prompt}; 
            final_response = await self.coordinator_agent.ainvoke(agent_input) # await ... ainvoke KULLAN
            final_output = final_response.get("output", "Final plan generation failed.")
            logging.info(f"[CompileNode] Agent Son Plan: {final_output}")
            return {"final_plan": final_output} # final_plan döndür
        except Exception as e: 
            logging.error(f"[CompileNode] HATA: {e}", exc_info=True); 
            return {"final_plan": f"Plan derlenirken hata: {type(e).__name__}."}

    # Karar verme fonksiyonları aynı
    def decide_after_parsing(self, state: TravelPlanState) -> str:
        if state.get("error_message"): return "compile_final_plan" 
        else: return "calculate_dates"
    def decide_after_dates(self, state: TravelPlanState) -> str:
        if state.get("error_message"): return "compile_final_plan"
        else: return "process_date_budget"

    # Graph oluşturma (Checkpointer İLE)
    def build_graph(self) -> Runnable:
        logging.info("LangGraph workflow'u oluşturuluyor (ASENKRON node'lar, Checkpointer İLE)...")
        workflow = StateGraph(TravelPlanState)
        
        # Node eklemeleri (ASENKRON fonksiyonlarla)
        workflow.add_node("parse_request", self.parse_request_node)
        workflow.add_node("calculate_dates", self.calculate_dates_node)
        workflow.add_node("process_date_budget", self.process_date_budget_node)
        workflow.add_node("process_destination", self.process_destination_node)
        workflow.add_node("compile_final_plan", self.compile_final_plan_node)
        
        workflow.set_entry_point("parse_request")

        # --- Koşullu Kenarları DÜZELT (start_node= OLMADAN) ---
        workflow.add_conditional_edges(
            "parse_request",             # Başlangıç node'u (konumsal argüman)
            path=self.decide_after_parsing,  # path= keyword'ü ile fonksiyon
            path_map={                   # path_map= keyword'ü ile dictionary
                "calculate_dates": "calculate_dates",
                "compile_final_plan": "compile_final_plan", 
            }
        )
        workflow.add_conditional_edges(
            "calculate_dates",           # Başlangıç node'u (konumsal argüman)
            path=self.decide_after_dates,    # path= keyword'ü ile fonksiyon
            path_map={                   # path_map= keyword'ü ile dictionary
                "process_date_budget": "process_date_budget",
                "compile_final_plan": "compile_final_plan",
            }
        )
        # --- ---

        # Direkt kenarlar aynı
        workflow.add_edge("process_date_budget", "process_destination")
        workflow.add_edge("process_destination", "compile_final_plan")
        workflow.add_edge("compile_final_plan", END)
        
        # Checkpointer'ı ekle
        try:
            from langgraph.checkpoint.memory import MemorySaver 
            app = workflow.compile(checkpointer=MemorySaver()) 
            logging.info("LangGraph workflow başarıyla derlendi (Travel System - Checkpointer ile).")
        except ImportError:
             logging.error("MemorySaver import edilemedi! Checkpointing olmadan devam edilemiyor.")
             raise 
        # except TypeError: # Eğer hala TypeError verirse, bu bloğu tekrar aktif edebilirsiniz
        #      logging.warning("Travel system compile checkpointer ile TypeError verdi, checkpointer olmadan deneniyor.")
        #      app = workflow.compile()

        return app

    # Ana çağrı metodu (ASENKRON)
    async def process_query(self, user_query: str) -> str: # async def OLMALI
        logging.info(f"process_query çağrıldı: {user_query}")
        initial_state = {"user_query": user_query}
        # Config thread_id'yi her seferinde farklı yapmak daha iyi olabilir
        import uuid
        config = {"configurable": {"thread_id": f"travel-thread-{uuid.uuid4()}"}} 
        try:
            final_state = await self.app.ainvoke(initial_state, config=config) # await ... ainvoke KULLAN
            # 'final_plan' anahtarını kullan
            final_plan_output = final_state.get("final_plan", "Hata: Nihai plan state'den alınamadı.")
            # ... (Hata loglama ve dönüş) ...
            if final_plan_output and ("error occurred" in final_plan_output.lower() or "oluştu" in final_plan_output.lower()): logging.error(f"Hata döndü: {final_plan_output}")
            else: logging.info("TravelPlanningSystem başarıyla tamamlandı (async).")
            return final_plan_output
        except Exception as e:
            logging.error(f"TravelPlanningSystem (async) hatası: {e}", exc_info=True)
            return f"Sistem hatası: {e}"