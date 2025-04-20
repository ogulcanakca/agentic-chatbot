# app/travel_system/workflow.py
# SENKRON HALİ

import json
import logging
from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
# Checkpointer senkron graph ile de kullanılabilir, şimdilik bırakalım
from langgraph.checkpoint.memory import MemorySaver

# Agent'ları ve araçları import et (Aynı kalır)
from .agents.coordinator_agent import create_coordinator_agent
from .agents.date_budget_agent import create_date_budget_agent
from .agents.destination_agent import create_destination_agent
from .tools.date_tools import calculate_travel_dates
from .tools.parsing_tools import parse_travel_query
# from .tools.destination_tools import get_tomtom_map_url # Kullanılıyorsa

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# State Tanımı (Aynı kalır)
class TravelPlanState(TypedDict):
    user_query: str
    origin: Optional[str]
    parsed_request: Optional[Dict[str, Any]]
    calculated_dates: Optional[Dict[str, str]]
    date_budget_summary: Optional[str]
    destination_summary: Optional[str]
    final_plan: Optional[str]
    error_message: Optional[str]

class TravelPlanningSystem:
    def __init__(self):
        logging.info("TravelPlanningSystem başlatılıyor (Senkron Versiyon)...")
        # Agent oluşturma fonksiyonlarının senkron executor döndürdüğünü varsayıyoruz
        self.coordinator_agent = create_coordinator_agent()
        self.date_budget_agent = create_date_budget_agent()
        self.destination_agent = create_destination_agent()
        self.app = self.build_graph()
        logging.info("TravelPlanningSystem başarıyla başlatıldı (Senkron Versiyon).")

    # --- Node Fonksiyonları (SENKRON) ---

    def parse_request_node(self, state: TravelPlanState) -> Dict[str, Any]: # def
        logging.info("[ParseNode] Çalıştırılıyor...")
        user_query = state['user_query']
        try:
            # Araçlar genellikle senkron çalışır
            parsed_info = parse_travel_query.func(user_query=user_query)
            logging.info(f"[ParseNode] Ayrıştırma Sonucu: {parsed_info}")
            error_message = parsed_info.get("error")
            required_fields = ["destination", "natural_language_date", "duration_days"]
            missing_fields = [field for field in required_fields if not parsed_info.get(field)]
            if missing_fields: error_message = parsed_info.get("error", f"Eksik bilgi: {', '.join(missing_fields)}"); logging.warning(f"[ParseNode] Eksik: {missing_fields}")
            return {
                "parsed_request": parsed_info,
                "origin": parsed_info.get("origin"),
                "error_message": error_message
            }
        except Exception as e: logging.error(f"[ParseNode] Hata: {e}", exc_info=True); return {"error_message": f"Sorgu ayrıştırılamadı: {e}"}

    def calculate_dates_node(self, state: TravelPlanState) -> Dict[str, Any]: # def
        logging.info("[CalculateDatesNode] Çalıştırılıyor...")
        # ... (İçerik aynı kalır, araç senkron) ...
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


    def process_date_budget_node(self, state: TravelPlanState) -> Dict[str, Any]: # def
        logging.info("[DateBudgetNode] Çalıştırılıyor...")
        # ... (Gerekli bilgileri alma kısmı aynı) ...
        parsed_info = state.get('parsed_request'); calculated_dates = state.get('calculated_dates')
        if not parsed_info or not calculated_dates: logging.warning("[DateBudgetNode] Bilgi eksik."); return {"date_budget_summary": "Skipped: Missing info."}
        destination = parsed_info.get('destination'); nl_date = parsed_info.get('natural_language_date'); start_date = calculated_dates.get('start_date'); end_date = calculated_dates.get('end_date'); duration = parsed_info.get('duration_days'); budget_amount = parsed_info.get('budget_amount', 'N/A'); budget_currency = parsed_info.get('budget_currency', '')
        if not all([destination, nl_date, start_date, end_date, duration is not None]): logging.warning("[DateBudgetNode] Alt bilgi eksik."); return {"date_budget_summary": "Skipped: Missing sub-keys."}

        date_budget_query = f"""Analyze the dates and budget for a trip.
        Destination: {destination}
        Dates: {nl_date} (Calculated as {start_date} to {end_date}, Duration: {duration} days)
        Budget: {budget_amount} {budget_currency}

        Provide a brief summary in TURKISH covering:
        1. Confirmation of dates and duration.
        2. Budget amount and currency. Mention if currency conversion might be needed (if not TRY).
        3. A very brief note if the budget seems reasonable for the destination/duration (optional, simple check).
        Respond ONLY with the summary. Do not add any extra text.
        """
        logging.info("[DateBudgetNode] Date Budget Agent çağrılıyor (SENKRON)...")
        try:
            agent_input = {"input": date_budget_query}
            # --- SENKRON ÇAĞRI ---
            response = self.date_budget_agent.invoke(agent_input)
            # --- ---
            logging.info(f"[DateBudgetNode] Agent Ham Yanıtı: {response}")
            summary = response.get("output", "Date/Budget summary error.")
            logging.info(f"[DateBudgetNode] Agent Özet Sonucu: {summary}")
            # Hata kontrolü (aynı kalabilir)
            error_in_summary = "error" in summary.lower() or "hata" in summary.lower()
            return {"date_budget_summary": summary, "error_message": state.get("error_message") or (f"DateBudget Agent Error: {summary}" if error_in_summary else None)}
        except Exception as e: logging.error(f"[DateBudgetNode] Hata: {e}", exc_info=True); error_msg = f"Error: {e}"; return {"date_budget_summary": error_msg, "error_message": error_msg}


    def process_destination_node(self, state: TravelPlanState) -> Dict[str, Any]: # def olduğundan emin ol
        logging.info("[DestinationNode] Çalıştırılıyor...")
        parsed_info = state.get('parsed_request'); calculated_dates = state.get('calculated_dates')
        origin_city = state.get('origin')

        # --- DETAYLI LOGLAMA BAŞLANGICI ---
        logging.debug(f"[DestinationNode] Gelen State['parsed_request']: {json.dumps(parsed_info, indent=2, ensure_ascii=False)}")
        logging.debug(f"[DestinationNode] Gelen State['calculated_dates']: {json.dumps(calculated_dates, indent=2, ensure_ascii=False)}")
        logging.debug(f"[DestinationNode] Gelen State['origin']: {origin_city}")
        # ---

        if not parsed_info or not calculated_dates:
            logging.warning("[DestinationNode] Kritik bilgi eksik (parsed_info veya calculated_dates).")
            # Hata mesajını daha açıklayıcı yapalım
            missing = []
            if not parsed_info: missing.append("parsed_info")
            if not calculated_dates: missing.append("calculated_dates")
            error_msg = f"Skipped: Missing critical info: {', '.join(missing)}."
            return {"destination_summary": error_msg, "error_message": state.get("error_message") or error_msg} # error_message'ı da güncelle

        destination_city = parsed_info.get('destination')
        start_date = calculated_dates.get('start_date')
        end_date = calculated_dates.get('end_date')
        budget_amount_ref = parsed_info.get('budget_amount', 'N/A') # Prompt için referans
        budget_currency_ref = parsed_info.get('budget_currency', '') # Prompt için referans

        # --- ÇIKARILAN BİLGİLERİ LOGLA ---
        logging.debug(f"[DestinationNode] Çıkarılan destination_city: {destination_city}")
        logging.debug(f"[DestinationNode] Çıkarılan start_date: {start_date}")
        logging.debug(f"[DestinationNode] Çıkarılan end_date: {end_date}")
        logging.debug(f"[DestinationNode] Çıkarılan budget_amount_ref: {budget_amount_ref}")
        logging.debug(f"[DestinationNode] Çıkarılan budget_currency_ref: {budget_currency_ref}")
        # ---

        # Gerekli alt bilgilerin kontrolü
        required_sub_keys = {"destination": destination_city, "start_date": start_date, "end_date": end_date}
        missing_sub_keys = [key for key, value in required_sub_keys.items() if not value]
        if missing_sub_keys:
            logging.warning(f"[DestinationNode] Gerekli alt bilgiler eksik: {', '.join(missing_sub_keys)}.")
            error_msg = f"Skipped: Missing sub-keys: {', '.join(missing_sub_keys)}."
            # Mevcut hataya ekleme yapalım veya yenisini oluşturalım
            current_error = state.get("error_message")
            new_error = f"{current_error + '; ' if current_error else ''}{error_msg}"
            return {"destination_summary": error_msg, "error_message": new_error}

        # Destination Agent prompt'unu oluştur (içeriği kontrol et)
        # --- PROMPT İÇERİĞİ ---
        # Önceki yanıtlarda paylaştığınız prompt içeriğinin burada
        # doğru değişkenlerle (destination_city, start_date, end_date, origin_city vb.)
        # eksiksiz olarak yer aldığından emin olun.
        destination_query = f"""
        Please collect detailed travel information for the following trip and provide the result as a Turkish summary:
        - Origin: {origin_city or 'Belirtilmemiş'}
        - Destination: {destination_city}
        - Start Date: {start_date}
        - End Date: {end_date}
        - Budget Information (for reference): {budget_amount_ref} {budget_currency_ref}

        Tasks & Output Structure (Use EXACT Turkish Headings):
        1. Use `search_city_info` for {destination_city}.
        2. Use `get_weather_forecast` for {destination_city} between {start_date} - {end_date}.
        3. Use `Google Hotels_with_tavily` for {destination_city} for dates {start_date} to {end_date}. Note limitations.
        4. Use `get_tomtom_map_url` with `city_name`='{destination_city}'.
        5. Combine results under: 'Şehir Bilgileri', 'Hava Durumu/Kıyafet Önerileri', 'Otel Seçenekleri', 'Harita Görünümü'. Include map URL if available. Respond ONLY in Turkish. If a tool fails, note it politely and continue.
        """
        # --- ---

        # --- OLUŞTURULAN PROMPT'U LOGLA ---
        logging.info(f"--- [DestinationNode] Destination Agent'a Gönderilecek SENKRON Prompt Başlangıcı ---")
        logging.info(destination_query)
        logging.info(f"--- [DestinationNode] Destination Agent'a Gönderilecek SENKRON Prompt Sonu ---")
        # ---

        logging.info("[DestinationNode] Destination Agent çağrılıyor (SENKRON)...")
        try:
            agent_input = {"input": destination_query}
            # SENKRON ÇAĞRI
            response = self.destination_agent.invoke(agent_input)

            # Agent'ın ham yanıtını logla
            logging.debug(f"[DestinationNode] Agent Ham Yanıtı: {response}")

            summary = response.get("output", "Destination summary error.")
            logging.info(f"[DestinationNode] Agent Özet Sonucu: {summary}")

            # Hata kontrolü
            error_in_summary = False
            if isinstance(summary, str):
                summary_lower = summary.lower()
                # Agent'ın hata mesajlarını daha iyi yakalamaya çalışalım
                if "error" in summary_lower or "hata" in summary_lower or "lütfen" in summary_lower or "belirtiniz" in summary_lower or "eksik" in summary_lower or "summary error" in summary_lower:
                    error_in_summary = True
                    logging.warning(f"[DestinationNode] Agent yanıtında potansiyel hata/eksik bilgi tespit edildi: {summary}")

            # Mevcut hataya ekleme yapalım veya yenisini oluşturalım
            current_error = state.get("error_message")
            new_error = current_error
            if error_in_summary:
                error_msg = f"Destination Agent Error/Incomplete: {summary}"
                new_error = f"{current_error + '; ' if current_error else ''}{error_msg}"

            return {"destination_summary": summary, "error_message": new_error}

        except Exception as e:
            logging.error(f"[DestinationNode] Agent çağrılırken Hata: {e}", exc_info=True)
            error_msg = f"Error calling Destination Agent: {type(e).__name__}"
            current_error = state.get("error_message")
            new_error = f"{current_error + '; ' if current_error else ''}{error_msg}"
            return {"destination_summary": f"Hata: {type(e).__name__}", "error_message": new_error}


    def compile_final_plan_node(self, state: TravelPlanState) -> Dict[str, Any]: # def
        logging.info("[CompileNode] Çalıştırılıyor...")

        # --- STATE KONTROL LOGLARI ---
        logging.debug(f"--- [CompileNode] Gelen State Başlangıcı ---")
        logging.debug(f"User Query: {state.get('user_query')}")
        logging.debug(f"Parsed Request: {state.get('parsed_request')}")
        logging.debug(f"Calculated Dates: {state.get('calculated_dates')}")
        logging.debug(f"Date Budget Summary: {state.get('date_budget_summary')}") # Bu önemli
        logging.debug(f"Destination Summary: {state.get('destination_summary')}") # Bu önemli
        logging.debug(f"Error Message: {state.get('error_message')}")
        logging.debug(f"--- [CompileNode] Gelen State Sonu ---")
        # --- ---

        error_msg = state.get("error_message")
        # Önceki hata kontrolü aynı kalabilir...
        if error_msg and ("parse" in error_msg.lower() or "date calculation failed" in error_msg.lower() or "ayrıştırılamadı" in error_msg.lower()):
            logging.error(f"[CompileNode] Kritik hata nedeniyle plan derlenemiyor: {error_msg}"); return {"final_plan": f"Plan oluşturulamadı. Temel bilgiler ayrıştırılamadı veya tarihler hesaplanamadı. Hata: {error_msg}"}
        # elif error_msg: logging.warning(f"[CompileNode] Kritik olmayan hata ile devam ediliyor: {error_msg}") # İsteğe bağlı

        # Özetleri state'den almayı dene
        date_budget_summary = state.get('date_budget_summary', 'Bütçe/Tarih Özeti Alınamadı') # Daha açıklayıcı varsayılan
        destination_summary = state.get('destination_summary', 'Hedef Bilgisi Özeti Alınamadı') # Daha açıklayıcı varsayılan
        parsed_info = state.get('parsed_request', {})
        calculated_dates = state.get('calculated_dates', {})
        start_date = calculated_dates.get('start_date', '?')
        end_date = calculated_dates.get('end_date', '?')

        # --- ALINAN ÖZETLERİ LOGLA ---
        logging.debug(f"[CompileNode] Alınan Date Budget Summary: {date_budget_summary[:200]}...") # Çok uzunsa kısalt
        logging.debug(f"[CompileNode] Alınan Destination Summary: {destination_summary[:200]}...") # Çok uzunsa kısalt
        # --- ---

        # Eğer özetler gerçekten alınamadıysa, prompt'u buna göre ayarla veya hata ver
        if date_budget_summary == 'Bütçe/Tarih Özeti Alınamadı' or destination_summary == 'Hedef Bilgisi Özeti Alınamadı':
            logging.error("[CompileNode] Kritik özet bilgileri state'de bulunamadı!")
            # return {"final_plan": "Plan derlenemedi: Önceki adımlardan özet bilgileri alınamadı."} # İsterseniz burada bitirebilirsiniz

        # Agent hatalarını belirtmek için prompt'u ayarla
        destination_summary_for_prompt = destination_summary
        if error_msg and "Destination Agent Error" in error_msg: # Sadece destination agent hatasını not et
            destination_summary_for_prompt = f"(Not: Hedef bilgileri alınırken sorun oluştu: {destination_summary})"
        elif error_msg and "DateBudget Agent Error" in error_msg: # Bütçe agent hatasını da not et
            # Bu durumda belki destination özetini de hata mesajı olarak göstermek daha iyi olabilir
            pass # Şimdilik sadece destination hatasını ele alıyoruz

        # Final prompt'u oluştur
        final_prompt = f"""
        Aşağıdaki bilgileri kullanarak kullanıcı için TÜRKÇE bir nihai seyahat planı özeti oluşturun.

        User Request: {state.get('user_query', 'N/A')}
        Parsed Info: {json.dumps(parsed_info, ensure_ascii=False, indent=2)}
        Calculated Dates: {start_date} - {end_date} (Duration: {parsed_info.get('duration_days', '?')} days)
        Origin: {parsed_info.get('origin', 'Belirtilmemiş')}

        --- Date/Budget Summary ---
        {date_budget_summary}
        --- End Date/Budget Summary ---

        --- Destination Summary (Includes City Info, Weather, Hotels, Map URL) ---
        {destination_summary_for_prompt}
        --- End Destination Summary ---

        Task: Tüm bu bilgileri sentezleyerek aşağıdaki TÜRKÇE başlıklarla bir plan oluşturun:
        1. Seyahat Özeti (Çıkış Yeri, Varış Yeri, Tarihler, Süre - Ayrıştırılmış Bilgiden)
        2. Bütçe ve Kur Bilgisi (Date/Budget Summary'den Alınmalı)
        3. Hava Durumu ve Kıyafet Önerileri (Destination Summary'den Alınmalı)
        4. Şehir ve Gezi Bilgileri (Destination Summary'den Alınmalı)
        5. Konaklama Önerileri (Destination Summary'den Alınmalı, sınırlamaları belirtin)
        6. Harita Görünümü (Destination Summary'den Harita URL'sini çıkarın ve ekleyin)

        Eğer bilgiler eksikse veya önceki adımlarda hata oluştuysa (özetlerde belirtildiği gibi), bunu nazikçe belirtin. Sadece derleme yapın, yeni araç çağırmayın. Yanıt SADECE TÜRKÇE olmalıdır.
        """
        # --- OLUŞTURULAN PROMPT'U LOGLA ---
        logging.info(f"--- [CompileNode] Coordinator Agent'a Gönderilecek SENKRON Prompt Başlangıcı ---")
        logging.info(final_prompt)
        logging.info(f"--- [CompileNode] Coordinator Agent'a Gönderilecek SENKRON Prompt Sonu ---")
        # ---

        logging.info("[CompileNode] Coordinator Agent çağrılıyor (SENKRON)...")
        try:
            agent_input = {"input": final_prompt}
            # SENKRON ÇAĞRI
            final_response = self.coordinator_agent.invoke(agent_input)

            logging.debug(f"[CompileNode] Coordinator Ham Yanıtı: {final_response}") # Debug seviyesinde logla

            final_output = final_response.get("output", "Final plan generation failed.")
            logging.info(f"[CompileNode] Agent Son Plan: {final_output}")
            return {"final_plan": final_output}
        except Exception as e:
            logging.error(f"[CompileNode] Coordinator çağrılırken HATA: {e}", exc_info=True)
            return {"final_plan": f"Plan derlenirken Coordinator Agent hatası oluştu: {type(e).__name__}."}

    def decide_after_parsing(self, state: TravelPlanState) -> str:
        if state.get("error_message") and ("parse" in state["error_message"].lower() or "ayrıştırılamadı" in state["error_message"].lower()):
             return "compile_final_plan" # Ayrıştırma hatası varsa direkt sona git
        else: return "calculate_dates" # Yoksa tarih hesaplamaya devam
    def decide_after_dates(self, state: TravelPlanState) -> str:
        if state.get("error_message") and "date calculation failed" in state["error_message"].lower():
             return "compile_final_plan" # Tarih hatası varsa direkt sona git
        else: return "process_date_budget" # Yoksa bütçeye devam
        
    # Graph oluşturma (SENKRON node'lar ile)
    def build_graph(self) -> Runnable:
        logging.info("LangGraph workflow'u oluşturuluyor (SENKRON node'lar)...")
        workflow = StateGraph(TravelPlanState)

        # Node eklemeleri (SENKRON fonksiyonlarla)
        workflow.add_node("parse_request", self.parse_request_node)
        workflow.add_node("calculate_dates", self.calculate_dates_node)
        workflow.add_node("process_date_budget", self.process_date_budget_node)
        workflow.add_node("process_destination", self.process_destination_node)
        workflow.add_node("compile_final_plan", self.compile_final_plan_node)

        workflow.set_entry_point("parse_request")

        # Koşullu kenarlar (Aynı kalır)
        workflow.add_conditional_edges(
            "parse_request",
            path=self.decide_after_parsing,
            path_map={
                "calculate_dates": "calculate_dates",
                "compile_final_plan": "compile_final_plan",
            }
        )
        workflow.add_conditional_edges(
            "calculate_dates",
            path=self.decide_after_dates,
            path_map={
                "process_date_budget": "process_date_budget",
                "compile_final_plan": "compile_final_plan",
            }
        )

        # Direkt kenarlar (Aynı kalır)
        workflow.add_edge("process_date_budget", "process_destination")
        workflow.add_edge("process_destination", "compile_final_plan")
        workflow.add_edge("compile_final_plan", END)

        # Checkpointer senkron invoke ile de çalışmalı
        try:
             # MemorySaver senkron invoke ile uyumludur
             app = workflow.compile(checkpointer=MemorySaver())
             logging.info("LangGraph workflow başarıyla derlendi (Travel System - Senkron, Checkpointer ile).")
        except ImportError:
             logging.error("MemorySaver import edilemedi! Checkpointing olmadan devam edilemiyor.")
             raise
        except Exception as e:
             logging.error(f"Graph derlenirken hata (checkpointer ile): {e}", exc_info=True)
             logging.warning("Checkpointer olmadan derleniyor...")
             app = workflow.compile() # Fallback to no checkpointer

        return app

    # Ana çağrı metodu (SENKRON)
    def process_query(self, user_query: str) -> str: # def
        logging.info(f"process_query (Senkron) çağrıldı: {user_query}")
        initial_state = {"user_query": user_query}
        # Config thread_id'yi her seferinde farklı yapalım
        import uuid
        config = {"configurable": {"thread_id": f"travel-sync-thread-{uuid.uuid4()}"}}
        try:
            # --- SENKRON ÇAĞRI ---
            final_state = self.app.invoke(initial_state, config=config)
            # --- ---
            final_plan_output = final_state.get("final_plan", "Hata: Nihai plan state'den alınamadı.")
            # Hata loglama (aynı kalabilir)
            if isinstance(final_plan_output, str) and ("error occurred" in final_plan_output.lower() or "oluştu" in final_plan_output.lower() or "failed" in final_plan_output.lower()):
                logging.error(f"TravelPlanningSystem (Senkron) hata döndürdü: {final_plan_output}")
            else:
                logging.info("TravelPlanningSystem (Senkron) başarıyla tamamlandı.")
            return final_plan_output
        except Exception as e:
            logging.error(f"TravelPlanningSystem (Senkron) process_query hatası: {e}", exc_info=True)
            return f"Sistem hatası oluştu: {type(e).__name__}"