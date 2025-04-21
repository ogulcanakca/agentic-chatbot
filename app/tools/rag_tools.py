# app/tools/rag_tools.py

import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import time

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.storage.database import get_or_create_collection, query_collection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Retrieves the most relevant documents from the ChromaDB collection for the given query.
def retrieve_documents(
    query: str,
    collection_name: str,
    n_results: int = 5,
    where_filter: Optional[Dict[str, Any]] = None,
    where_document_filter: Optional[Dict[str, Any]] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    
    # The query text and collection name cannot be empty, so we check again.
    if not query:
        logging.warning("Document retrieval cannot be done with an empty query string.")
        return []
    if not collection_name:
         logging.error("Document retrieval cannot be done without specifying the collection name.")
         return []

    # Start measuring the time of the document retrieval process
    function_start_time = time.time()
    logging.info(f"Searching for {n_results} results for query '{query}' in the '{collection_name}' collection...")
    
    # Logging filter information
    if where_filter: logging.info(f"  Metadata Filter: {where_filter}")
    # If there is a document filter and it's different from the metadata filter, we log it.
    if where_document_filter: logging.info(f"  Document Filter: {where_document_filter}")
    # If there is a score threshold, we log it.
    if score_threshold: logging.info(f"  Distance Threshold: < {score_threshold}")

    retrieved_docs = []
    # Get or create the collection
    collection = get_or_create_collection(collection_name)

    # Start measuring the query time
    query_start_time = time.time()
    # Perform the query and retrieve the results
    results = query_collection(
        collection=collection,
        query_texts=[query],
        n_results=n_results,
        where_filter=where_filter,
        where_document_filter=where_document_filter,
        include=["metadatas", "documents", "distances"]
    )
    # End query time measurement and log it
    query_end_time = time.time()
    logging.info(f"Database query completed in {query_end_time - query_start_time:.3f} seconds.")

    # The results come in a nested list structure
    if results and results.get('ids') and results['ids'][0]:
        # We always use index [0] since we sent a single query
        ids = results['ids'][0]
        # If there are documents, metadata, and distance information in the results, we get them.
        documents = results['documents'][0] if results.get('documents') else [None] * len(ids)
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(ids)
        distances = results['distances'][0] if results.get('distances') else [None] * len(ids)

        # Iterate over each result
        for i, doc_id in enumerate(ids):
            # Get the distance value at index i in the list.
            # This value is the vector distance of the document from the query vector.
            distance = distances[i]
            # Check if the score threshold is met
            if score_threshold is not None and distance is not None and distance >= score_threshold:
                logging.debug(f"Document (ID: {doc_id}, Distance: {distance:.4f}) skipped due to threshold ({score_threshold}).")
                continue  # Skip documents that don't meet the threshold

            # Add documents that pass the threshold to the list
            retrieved_docs.append({
                "id": doc_id,
                "document": documents[i] if documents else None,
                "metadata": metadatas[i] if metadatas else {},
                "distance": distance
            })

        logging.info(f"Query resulted in {len(ids)} documents, {len(retrieved_docs)} passed the threshold (if any) and are returned.")
    else:
        logging.info("Database query returned no results.")

    # Measure and log the total time for the document retrieval process.
    function_end_time = time.time()
    logging.info(f"retrieve_documents completed in {function_end_time - function_start_time:.3f} seconds.")
    
    # If no results, return an empty list
    return retrieved_docs

# Defines a function to convert a list of documents into a readable block of text that can be added to an LLM prompt.
def format_context(retrieved_docs: List[Dict[str, Any]]) -> str:
    # If no documents are retrieved, return an empty string for the prompt
    if not retrieved_docs:
        logging.info("No documents found to format, returning empty context.")
        return ""

    # Define a list to store the formatted documents
    context_parts = []
    # Add a more distinct separator between documents
    separator = "\n\n--- Source Separator ---\n\n"

    logging.info(f"Formatting {len(retrieved_docs)} documents for LLM context...")

    # Loop through each document and format it
    for i, doc in enumerate(retrieved_docs):
        doc_content = doc.get('document', '').strip()
        # Skip this source if the content is empty
        if not doc_content: 
            logging.warning(f"Source {i+1} (ID: {doc.get('id')}) content is empty, skipping formatting.")
            continue
        
        # Get metadata information and format it
        context_part = f"Source {i+1}:\n{doc_content}"
        # Add metadata information to the context_parts list
        context_parts.append(context_part)

    # Join all formatted parts together
    formatted_context = separator.join(context_parts)
    
    return formatted_context
