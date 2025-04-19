# agentic_chatbot_projectapp/travel_system/travel_planning.py

import json
from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver
import logging

# Agent'larımı ve araçlarımı import ediyorum
# Doğru Göreli İmportlar:
from .agents.coordinator_agent import create_coordinator_agent  # '.' aynı dizindeki 'agents' klasörüne işaret eder
from .agents.date_budget_agent import create_date_budget_agent
from .agents.destination_agent import create_destination_agent
from .tools.date_tools import calculate_travel_dates      # '.' aynı dizindeki 'tools' klasörüne işaret eder
from .tools.parsing_tools import parse_travel_query

# Graph'ın state yapısını tanımlıyorum. Akış boyunca bu bilgiler taşınacak.
class TravelPlanState(TypedDict):
    user_query: str
    parsed_request: Optional[Dict[str, Any]]
    calculated_dates: Optional[Dict[str, str]]
    date_budget_summary: Optional[str]
    destination_summary: Optional[str]
    final_plan: Optional[str]
    error_message: Optional[str]

# Ana seyahat planlama sistemimi sınıf olarak tanımlıyorum.
class TravelPlanningSystem:
    def __init__(self):
        # Sınıf başlatıldığında agent'larımı oluşturulacak.
        self.coordinator_agent = create_coordinator_agent()
        self.date_budget_agent = create_date_budget_agent()
        self.destination_agent = create_destination_agent()

        # LangGraph workflow da oluşturulacak.
        self.app = self.build_graph()

    # Kullanıcı sorgusunu ayrıştırma işleminin yapıldığı node
    async def parse_request_node(self, state: TravelPlanState) -> Dict[str, Any]:

        user_query = state['user_query']
        try:
            # parse_travel_query tool'umu doğrudan kullanıyorum.
            parsed_info = parse_travel_query.func(user_query=user_query)
            # Gerekli bilgiler (hedef, tarih, süre) eksikse veya hata varsa belirtiyorum.
            if "error" in parsed_info or not all(k in parsed_info for k in ["destination", "natural_language_date", "duration_days"]):
                 return {"error_message": "Failed to parse essential travel details (destination, date, duration)."}
            # Başarılı olursa ayrıştırılmış bilgiyi ve hata olmadığını state'e ekliyorum.
            return {"parsed_request": parsed_info, "error_message": None}
        except Exception as e:
            return {"error_message": f"An unexpected error occurred during parsing: {e}"}

    # Seyahat tarihlerini hesaplama işleminin yapıldığı node.
    async def calculate_dates_node(self, state: TravelPlanState) -> Dict[str, Any]:
        parsed_info = state.get('parsed_request')
        # Eğer önceki adımdan ayrıştırılmış bilgi gelmediyse hata verecek
        if not parsed_info:
            return {"error_message": "Cannot calculate dates without parsed info."}
        try:
            # calculate_travel_dates tool'umu kullanıyorum.
            dates_result = calculate_travel_dates.func(
                natural_language_date=parsed_info["natural_language_date"],
                duration_days=parsed_info["duration_days"]
            )
            # Tool'dan hata dönerse belirtiyorum.
            if "error" in dates_result:
                return {"error_message": f"Date calculation failed: {dates_result['error']}"}
            return {"calculated_dates": dates_result, "error_message": None}
        except Exception as e:
            return {"error_message": f"Error calculating dates: {e}"}

    # Tarih ve bütçe bilgilerini işleme node'u
    async def process_date_budget_node(self, state: TravelPlanState) -> Dict[str, Any]:
        parsed_info = state.get('parsed_request')
        calculated_dates = state.get('calculated_dates')
        if not parsed_info or not calculated_dates:
            return {"date_budget_summary": "Skipped: Missing required info for budget processing."}

        start_date = calculated_dates['start_date']
        end_date = calculated_dates['end_date']

        # Tarih & Bütçe Agent'ım için prompt.
        # Sadece son özetin Türkçe olmasını istiyorum.
        date_budget_query = f"""
        Please create a summary of the dates and budget for the following travel details:
        - Destination: {parsed_info['destination']}
        - Specified Date Expression: {parsed_info['natural_language_date']}
        - Calculated Start: {start_date}
        - Calculated End: {end_date}
        - Duration of Stay: {parsed_info['duration_days']} days
        - Budget: {parsed_info.get('budget_amount', 'Not Specified')} {parsed_info.get('budget_currency', 'TRY')}

        Tasks:
        1. Use the `get_exchange_rates_and_budget` tool to evaluate the budget and obtain the relevant exchange rates (TRY, EUR, USD).
        2. Use the `calculate_travel_dates` tool to verify the dates (start: {start_date}, end: {end_date}).
        3. Combine this information to provide a summary in Turkish. Example: "Seyahat Tarihleri: {{start_date}} - {{end_date}}. Bütçe Değerlendirmesi: [evaluation from tool]. Kurlar: [rates from tool]..."
        """
        try:
            response = await self.date_budget_agent.ainvoke({"input": date_budget_query})
            summary = response.get("output", "Date and budget summary could not be generated by agent.")
            logging.info(f"[DateBudgetNode] Agent Sonucu: {summary}") # Agent sonucunu logla
            return {"date_budget_summary": summary}
        except Exception as e:
             logging.error(f"[DateBudgetNode] Hata: {e}", exc_info=True) # Hata logunu detaylandır
             return {"date_budget_summary": f"Error generating date/budget summary: {e}"}

    # Gidilecek yer hakkında bilgi toplama node'u.
    async def process_destination_node(self, state: TravelPlanState) -> Dict[str, Any]:
        parsed_info = state.get('parsed_request')
        calculated_dates = state.get('calculated_dates')
        # Gerekli bilgiler yoksa atlıyorum.
        if not parsed_info or not calculated_dates:
           return {"destination_summary": "Skipped: Missing required info for destination processing."}

        start_date = calculated_dates['start_date']
        end_date = calculated_dates['end_date']

        # Destinasyon Agent'ım için prompt..
        # Sadece son özetin Türkçe olmasını istiyorum.
        destination_query = f"""
        Please collect detailed travel information for the following destination and dates, and provide the result as a Turkish summary:
        - Destination: {parsed_info['destination']}
        - Start Date: {start_date}
        - End Date: {end_date}
        - Budget Information (for reference): {parsed_info.get('budget_amount', 'N/A')} {parsed_info.get('budget_currency', '')}

        Tasks:
        1. Use `search_city_info` to gather general information about {parsed_info['destination']} (historical sites, popular spots, etc.).
        2. Use `get_weather_forecast` to get the weather forecast and outfit suggestions for {start_date} - {end_date}.
        3. Use `Google Hotels_with_tavily` to research suitable hotel options for the specified dates (using the budget as reference if available). Try to include price and location details.
        4. Combine the outputs from these three tools to provide a comprehensive Turkish summary about the destination (under Turkish headings: City Information, Weather/Outfit, Hotel Options).
        """
        try:
            response = await self.destination_agent.ainvoke({"input": destination_query})
            summary = response.get("output", "Destination summary could not be generated by agent.") 
            return {"destination_summary": summary}
        except Exception as e:
            return {"destination_summary": f"Error generating destination summary: {e}"}

    # Tüm bilgileri birleştirip nihai planı oluşturma işleminin yapıldığı node.
    async def compile_final_plan_node(self, state: TravelPlanState) -> Dict[str, Any]:
        error_msg = state.get("error_message")
        # Eğer kritik bir hata mesajı varsa (ayrıştırma veya tarih hesaplama gibi) planı oluşturmuyorum.
        if error_msg and ("parse" in error_msg.lower() or "date calculation failed" in error_msg.lower()):
             return {"final_plan": f"Could not generate travel plan. Critical Error: {error_msg}"}
        # Kritik olmayan bir hata varsa, bunu belirterek derlemeye devam ediyorum.
        elif error_msg:
             print(f"!!! Compiling final plan despite previous error: {error_msg}")

        # Koordinatör Agent'ım için İngilizce prompt'u.
        # Sadece son çıktının Türkçe ve belirtilen başlıklarla olmasını istiyorum.
        parsed_info = state.get('parsed_request', {})
        calculated_dates = state.get('calculated_dates', {})
        start_date = calculated_dates.get('start_date', 'Unknown')
        end_date = calculated_dates.get('end_date', 'Unknown')

        final_prompt = f"""
        Using the following information, create a final travel plan summary for the user. Present the response in Turkish and in a user-friendly format.

        User Request: {state['user_query']}
        Parsed Information: {json.dumps(parsed_info, ensure_ascii=False, indent=2)}
        Calculated Dates: {start_date} - {end_date}

        Date and Budget Summary (from Date & Budget Agent):
        {state.get('date_budget_summary', 'Date and budget information could not be retrieved.')}

        Destination Information Summary (from Destination Agent):
        {state.get('destination_summary', 'Destination information could not be retrieved.')}

        Task:
        Synthesize this information to create a fluent and readable Turkish travel plan including the following headings:
        1.  **Travel Summary:** Destination, exact dates ({start_date} - {end_date}), and duration.
        2.  **Budget and Currency:** Integrate the summary from the Date & Budget Agent here (budget evaluation and exchange rates).
        3.  **Weather and Outfit:** Add the weather summary and outfit recommendations from the Destination Agent here.
        4.  **Places to Visit:** Include the city information and suggested popular/historical sites from the Destination Agent here.
        5.  **Accommodation Recommendations:** Include the hotel options summary from the Destination Agent here.

        If some summary information is missing or contains an error message, kindly note this politely in the final Turkish output. The Coordinator should not call any tools again, only compile the information.
        """
        try:
            final_response = await self.coordinator_agent.ainvoke({"input": final_prompt})
            final_output = final_response.get("output", "Final plan could not be generated by coordinator agent.")
            logging.info(f"[CompileNode] Agent Sonucu (Nihai Plan): {final_output}") # Agent sonucunu logla
            return {"final_plan": final_output}
        except Exception as e:
            logging.error(f"[CompileNode] Hata: {e}", exc_info=True) # Hata logunu detaylandır
            return {"final_plan": f"An unexpected error occurred during final plan compilation: {e}"}

    # Karar verme fonksiyonlarım (koşullu kenarlar için).
    def decide_after_parsing(self, state: TravelPlanState) -> str:
        if state.get("error_message"):
            return "compile_final_plan" 
        else:
            return "calculate_dates"

    # Tarih hesaplama sonrası nereye gidileceğini belirtiyorum.
    def decide_after_dates(self, state: TravelPlanState) -> str:
        if state.get("error_message"):
            return "compile_final_plan"
        else:
            return "process_date_budget"

    # LangGraph graph'ını oluşturan ve derleyen dahili metodum.
    def build_graph(self) -> Runnable:
        # StateGraph nesnemi oluşturuyorum, state tanımımı veriyorum.
        workflow = StateGraph(TravelPlanState)

        # Node'ları graph'a ekliyorum, isimlerini ve çalıştırılacak metodlarımı bağlıyorum.
        workflow.add_node("parse_request", self.parse_request_node)
        workflow.add_node("calculate_dates", self.calculate_dates_node)
        workflow.add_node("process_date_budget", self.process_date_budget_node)
        workflow.add_node("process_destination", self.process_destination_node)
        workflow.add_node("compile_final_plan", self.compile_final_plan_node)

        # Graph'ın başlangıç noktasını belirliyorum.
        workflow.set_entry_point("parse_request")

        # Node'lar arasındaki koşullu geçişleri tanımlıyorum.
        workflow.add_conditional_edges(
            "parse_request",             
            self.decide_after_parsing,  
            {                          
                "calculate_dates": "calculate_dates",
                "compile_final_plan": "compile_final_plan", 
            }
        )
        workflow.add_conditional_edges(
            "calculate_dates",
            self.decide_after_dates,
            {
                "process_date_budget": "process_date_budget",
                "compile_final_plan": "compile_final_plan",
            }
        )
        #  Node'lar arasındaki direkt geçişleri yanımlıyorum
        workflow.add_edge("process_date_budget", "process_destination")
        workflow.add_edge("process_destination", "compile_final_plan")
        workflow.add_edge("compile_final_plan", END)

        app = workflow.compile(checkpointer=MemorySaver())
        return app

    # Kullanıcının sorgusunu işlemek için main.py'den çağrılacak asenkron metodum.
    async def process_query(self, user_query: str) -> str:
        initial_state = {"user_query": user_query}

        config = {"configurable": {"thread_id": "my-travel-thread-123"}}

        try:
            final_state = await self.app.ainvoke(initial_state, config=config)
            final_plan_output = final_state.get("final_plan", "An error occurred and the final plan could not be generated.")
            return final_plan_output
        except Exception as e:
            return f"An unexpected error occurred while processing the travel plan: {e}"