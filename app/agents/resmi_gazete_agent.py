# app/agents/resmi_gazete_agent.py

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.tools.rag_tools import retrieve_documents, format_context
from app.core.llm import get_llm

from configs.agent_config import RESMI_GAZETE_COLLECTION, NUM_DOCUMENTS_TO_RETRIEVE, PROMPT_TEMPLATE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Function used to generate an answer using relevant documents
def generate_resmi_gazete_answer(state: Dict[str, Any]) -> Dict[str, Any]:

    logging.info("Resmi Gazete Agent is running...")
    query: Optional[str] = state.get("query")
    final_answer: Optional[str] = None
    retrieved_context: Optional[str] = None
    source_info = f"Resmi Gazete (Collection: {RESMI_GAZETE_COLLECTION})"  # Detailed source info

    # Check whether query exists or not
    if not query:
        logging.error("Resmi Gazete Agent: No valid 'query' found in the state.")
        final_answer = "I received an unrecognized or incomplete query. Please try rephrasing your question."
        source_info += " (Error: Missing Query)"
        return {"answer": final_answer, "context": None, "source": source_info}

    logging.info(f"Query to be processed: '{query}'")

    # Retrieve relevant documents
    logging.debug(f"Fetching documents from collection '{RESMI_GAZETE_COLLECTION}'...")
    try:
        retrieved_docs = retrieve_documents(
            query=query,
            collection_name=RESMI_GAZETE_COLLECTION,
            n_results=NUM_DOCUMENTS_TO_RETRIEVE
        )
    except Exception as e:
        logging.error(f"Error occurred while retrieving documents: {e}", exc_info=True)
        final_answer = "An issue occurred while accessing Resmi Gazete documents."
        source_info += " (Error: Document Retrieval)"
        return {"answer": final_answer, "context": None, "source": source_info}

    # If no relevant documents were found
    if not retrieved_docs:
        logging.warning("No relevant Resmi Gazete document found for the query.")
        final_answer = f"I couldn't find a Resmi Gazete document directly related to your query '{query}'. You can try again with different keywords."
        source_info += " (No Results Found)"
        retrieved_context = None
    # Or if the documents were not formatted properly, don't send an empty context to the LLM
    else:
        logging.info(f"{len(retrieved_docs)} relevant document(s) found.")
        try:
            retrieved_context = format_context(retrieved_docs)
            if not retrieved_context:  # If formatted context returns an empty string (e.g., no content)
                logging.warning("Documents found but formatted context is empty.")
                final_answer = "Relevant documents were found but their content was either empty or unprocessable."
                source_info += " (Error: Empty Context)"
                retrieved_context = "Formatted context is empty."
            else:
                # Context successfully formatted, ready to send to LLM
                pass
        except Exception as e:
            logging.error(f"Error occurred while formatting context: {e}", exc_info=True)
            final_answer = "An issue occurred while processing Resmi Gazete documents."
            source_info += " (Error: Formatting)"
            retrieved_context = f"Formatting Error: {e}"
            return {"answer": final_answer, "context": retrieved_context, "source": source_info}

    # If context exists and no error yet, generate answer using LLM
    if retrieved_context and not final_answer:
        try:
            # Get default LLM instance from app.core.llm
            logging.debug("Getting LLM instance...")
            llm = get_llm()

            # Prepare prompt to send to LLM
            prompt = PROMPT_TEMPLATE.format(query=query, context=retrieved_context)
            logging.debug(f"Prompt to be sent to LLM (first 500 chars):\n{prompt[:500]}...")

            # Invoke LLM and get response
            logging.info("Calling LLM (generate_resmi_gazete_answer)...")
            llm_response = llm.invoke(prompt)
            final_answer = llm_response.content.strip()
            logging.info("Received response from LLM.")
            source_info += " (Generated via RAG)"
        except Exception as e:
            logging.error(f"Error during LLM generation for Resmi Gazete answer: {e}", exc_info=True)
            final_answer = "Relevant information was found, but there was a problem synthesizing the answer."
            source_info += " (Error: LLM)"

    logging.info(f"Resmi Gazete Agent finished. Answer (first 100 characters): '{final_answer[:100] if final_answer else 'None'}'")
    return {"answer": final_answer, "context": retrieved_context, "source": source_info}
