# app/agents/travel_agent.py

import logging
import sys
from pathlib import Path
from typing import Dict, Any

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

def handle_travel_query(state: Dict[str, Any]) -> Dict[str, Any]:
    logging.info("Travel Agent is running (SYNCHRONOUS MODE)...")
    query: str = state.get("query", "")
    pdf_path: str | None = None
    answer: str = "Travel plan could not be generated."

    travel_system = None
    pdf_saver = None
    try:
        from app.travel_system.workflow import TravelPlanningSystem
        from app.travel_system.utils.pdf_saver import TravelPDFSaver
        try:
            travel_system = TravelPlanningSystem()
            logging.info("TravelPlanningSystem (Synchronous) started successfully.")
        except Exception as system_err:
            logging.error(f"Error while starting TravelPlanningSystem (Synchronous): {system_err}", exc_info=True)
            return {"answer": f"Travel system could not be started: {type(system_err).__name__}", "source": "Travel Agent (Error)"}

        try:
            pdf_saver = TravelPDFSaver(
                font_dir=str(project_root / "assets/fonts"),
                output_dir=str(project_root / "plans")
            )
            logging.info("TravelPDFSaver started successfully.")
        except FileNotFoundError as fnf_error:
            logging.warning(f"PDF Saver could not be started (Font file error): {fnf_error}. PDF will not be saved.")
            pdf_saver = None
        except Exception as saver_err:
            logging.error(f"General error while starting PDF Saver: {saver_err}")
            pdf_saver = None

    except ImportError as e:
        logging.error(f"Could not import travel system or PDF saver components: {e}")
        return {"answer": "Travel planning system components not found.", "source": "Travel Agent (Error)"}

    if not query:
        logging.warning("Travel Agent: No query found in state.")
        return {"answer": "Please enter a travel query.", "source": "Travel Agent (Error)"}

    try:
        logging.info(f"Query to be sent to TravelPlanningSystem (Synchronous): '{query}'")

        final_plan = travel_system.process_query(query)

        logging.info("TravelPlanningSystem (Synchronous) completed.")

        if final_plan and isinstance(final_plan, str) and not final_plan.startswith("An error occurred") and not final_plan.startswith("Could not generate"):
            answer = final_plan
            logging.info("Travel plan generated successfully.")
            if pdf_saver:
                try:
                    base_filename = pdf_saver.extract_title(final_plan)
                    pdf_path = pdf_saver.save_travel_plan_to_pdf(final_plan, filename=base_filename)
                    logging.info(f"Travel plan saved as PDF: {pdf_path}")
                except AttributeError:
                    logging.error("'extract_title' method not found in PDF Saver.")
                except Exception as pdf_err:
                    logging.error(f"Travel plan could not be saved as PDF: {pdf_err}", exc_info=True)
            else:
                logging.info("PDF was not saved because PDF Saver was not initialized or not available.")
        else:
            error_detail = final_plan if isinstance(final_plan, str) else "Returned result in invalid format."
            logging.error(f"TravelPlanningSystem (Synchronous) returned an error or invalid/empty result: {error_detail}")
            answer = final_plan if final_plan else "An unexpected result was received."

    except Exception as e:
        logging.error(f"Unexpected error occurred during Travel Agent (Synchronous): {e}", exc_info=True)
        answer = f"An unexpected error occurred while processing the travel plan: {type(e).__name__}"

    return {
        "answer": answer,
        "source": "Travel Agent (Synchronous)" + (f" (PDF: {Path(pdf_path).name})" if pdf_path else ""),
        "pdf_path": pdf_path
    }
