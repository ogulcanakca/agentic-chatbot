# app/storage/database.py

import chromadb
from chromadb.utils import embedding_functions
import logging
from pathlib import Path
import sys
from typing import List, Dict, Optional, Any

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.app_config import MODEL_NAME, CHROMA_DATA_PATH, create_chroma_data_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Running our function to create the folder where ChromaDB will be located
create_chroma_data_path()

# Global variable for storing the ChromaDB client object with a simple cache mechanism
client: Optional[chromadb.Client] = None

# Global variable for storing the embedding function with a simple cache mechanism
embedding_function: Optional[embedding_functions.SentenceTransformerEmbeddingFunction] = None

# Function to load the model
def get_embedding_function(embedding_model_name: str = MODEL_NAME) -> embedding_functions.SentenceTransformerEmbeddingFunction:
    global embedding_function
    # If the embedding function has not been created before, we create a new one
    if embedding_function is None:
        logging.info(f"Creating '{embedding_model_name}' embedding function for ChromaDB...")
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model_name
            )
    return embedding_function

# Function to start the ChromaDB client
def get_chroma_client() -> chromadb.Client:
    global client
    # If the client has not been created before, we create a new one
    if client is None:
        logging.info(f"Starting ChromaDB client (path: {CHROMA_DATA_PATH})...")
        client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
    return client

# Function to get or create a ChromaDB collection
def get_or_create_collection(collection_name: str, embedding_model_name: str = MODEL_NAME) -> Optional[chromadb.Collection]:

    client = get_chroma_client()
    emb_func = get_embedding_function(embedding_model_name)

    logging.info(f"Getting or creating '{collection_name}' collection (Embedding: {embedding_model_name})...")
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=emb_func, 
        metadata={"hnsw:space": "cosine"}  # We prefer Cosine Similarity for text embeddings
    )
    logging.info(f"'{collection_name}' collection successfully fetched/created. Number of records: {collection.count()}")
    return collection

# Function to add data to a ChromaDB collection
def add_data_to_collection(collection: chromadb.Collection,
                           ids: List[str],
                           documents: Optional[List[str]] = None,
                           embeddings: Optional[List[List[float]]] = None,
                           metadatas: Optional[List[Dict[str, Any]]] = None) -> bool:

    # Check if the list of IDs to be checked is empty
    if not ids:
        logging.warning("ID list for data to be added is empty.")
        return False
    num_items = len(ids)

    # If both documents and embeddings are None, raise an error
    if documents is None and embeddings is None:
        logging.error("'documents' or 'embeddings' parameter must be provided to add data.")
        return False
    # If both documents and embeddings are provided, prefer to use embeddings
    if documents is not None and embeddings is not None:
        logging.warning("Both 'documents' and 'embeddings' are provided. Priority will be given to 'embeddings'.")

    # Check if the number of IDs matches the number of documents
    if documents is not None and len(documents) != num_items:
        logging.error(f"Number of IDs ({num_items}) does not match number of documents ({len(documents)}).")
        return False
    
    # Check if the number of embeddings matches the number of IDs
    if embeddings is not None and len(embeddings) != num_items:
        logging.error(f"Number of IDs ({num_items}) does not match number of embeddings ({len(embeddings)}).")
        return False
    
    # Check if the number of metadata matches the number of IDs
    if metadatas is not None and len(metadatas) != num_items:
        logging.error(f"Number of IDs ({num_items}) does not match number of metadata ({len(metadatas)}).")
        return False
    
    # If metadata is None, create a list of empty dictionaries
    safe_metadatas = metadatas if metadatas is not None else [{} for _ in range(num_items)]

    # Perform the data addition
    try:
        logging.info(f"Adding {num_items} records to '{collection.name}' collection...")
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,   
            metadatas=safe_metadatas
        )
        logging.info(f"{num_items} records successfully added. Total records in the collection: {collection.count()}")
        return True
    except Exception as e:
        if "ID already exists" in str(e):
             logging.error("Error: Some of the IDs you are trying to add already exist in the collection.")
        return False

# Function to query a ChromaDB collection
def query_collection(collection: chromadb.Collection,
                     query_texts: Optional[List[str]] = None,
                     query_embeddings: Optional[List[List[float]]] = None,
                     n_results: int = 5,
                     where_filter: Optional[Dict[str, Any]] = None,
                     where_document_filter: Optional[Dict[str, Any]] = None,
                     include: List[str] = ["metadatas", "documents", "distances"]) -> Optional[Dict[str, Any]]:

    # Check if either query_texts or query_embeddings is provided
    if query_texts is None and query_embeddings is None:
        logging.error("'query_texts' or 'query_embeddings' must be provided for querying.")
        return None
    
    # If both query_texts and query_embeddings are provided, prefer query_texts
    if query_texts is not None and query_embeddings is not None:
        logging.warning("Both 'query_texts' and 'query_embeddings' are provided. 'query_texts' will be used.")
        query_embeddings = None 

    results = collection.query(
        query_texts=query_texts,
        query_embeddings=query_embeddings,
        n_results=n_results,
        where=where_filter,
        where_document=where_document_filter,
        include=include
    )
    logging.info("Query completed.")
    
    # Check if any results were returned
    if results and results.get('ids'):
            # Log the number of results found for each query
            for i, ids_list in enumerate(results['ids']):
                logging.debug(f"  {i+1} query found {len(ids_list)} results.")
    else:
            logging.info("No results found for the query.")
    return results
