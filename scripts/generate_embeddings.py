# scripts/generate_embeddings.py

import json
import logging
import sys
from pathlib import Path
import time
from typing import List, Dict, Any, Tuple, Iterator

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.utils.embedding import generate_embeddings, get_embedding_model
from app.storage.database import get_or_create_collection, add_data_to_collection, get_chroma_client
from configs.script_config import DATA_FOLDERS, PROCESSED_DATA_DIR, PROCESSING_BATCH_SIZE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Function for reading our processed data in JSON format in batches
def read_processed_data_batch(file_path: Path, batch_size: int) -> Iterator[Tuple[List[str], List[str], List[Dict[str, Any]]]]:

    # Empty lists for batches
    batch_ids: List[str] = []
    batch_documents: List[str] = []
    batch_metadatas: List[Dict[str, Any]] = []
    processed_line_count = 0

    # Since each processed data (news) is on its own line,
    # we read and process the file line by line
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                processed_line_count = i + 1
                try:
                    record = json.loads(line.strip())
                    doc_id = record.get('id')
                    doc_text = record.get('text')
                    doc_metadata = record.get('metadata')

                    # Performing basic checks for the existence and type of ID, text, and metadata
                    if not doc_id or not isinstance(doc_id, (str, int)):
                        logging.warning(f"Line {processed_line_count}: Invalid or missing 'id', skipping.")
                        continue
                    if not doc_text or not isinstance(doc_text, str):
                        logging.warning(f"Line {processed_line_count}: Invalid or missing 'text', skipping.")
                        continue
                    if doc_metadata is None or not isinstance(doc_metadata, dict):
                        doc_metadata = {}

                    # Add IDs and texts to the batch lists
                    batch_ids.append(str(doc_id))
                    batch_documents.append(doc_text)
                    batch_metadatas.append(doc_metadata)

                    # If the batch lists have reached the batch size, yield them and reset
                    # We use yield instead of return to reduce memory load by sending data as soon as the batch size is reached
                    if batch_size is not None and batch_size > 0 and len(batch_ids) >= batch_size:
                        yield batch_ids, batch_documents, batch_metadatas
                        batch_ids, batch_documents, batch_metadatas = [], [], []

                # Log JSON decode errors or other unexpected errors
                except json.JSONDecodeError:
                    logging.warning(f"Line {processed_line_count}: Invalid JSON format, skipping: {line.strip()}")
                    continue
                except Exception as e:
                    logging.error(f"Unexpected error processing line {processed_line_count}: {e}", exc_info=True)
                    continue  # Skip this line and continue

        # Yield any remaining data less than PROCESSING_BATCH_SIZE as a batch after processing the file
        if batch_ids:
            yield batch_ids, batch_documents, batch_metadatas

    # Log errors when reading the file and return empty lists
    except IOError as e:
        logging.error(f"Could not read processed data file: {file_path}. Error: {e}")
        yield [], [], []
    except Exception as e:
        logging.error(f"General error while reading data ({file_path}): {e}", exc_info=True)
        yield [], [], []

# Define our function to process the data source, generate embeddings, and add to the database
def process_and_add_batch(collection, ids, documents, metadatas) -> int:

    # If IDs list is empty, return 0, skip the batch and do not generate embeddings
    if not ids:
        return 0
    
    batch_start_time = time.time()
    logging.debug(f"Processing batch of {len(ids)} items for collection '{collection.name}'...")

    # Generate embeddings
    embeddings = generate_embeddings(documents)

    # If embeddings are empty or don't match the IDs count, log an error and return 0
    if not embeddings or len(embeddings) != len(ids):
        logging.error(f"Could not generate embeddings for the batch or count mismatch ({len(embeddings)} vs {len(ids)}). This batch will not be added to the database.")
        return 0 

    # Add data to ChromaDB
    success = add_data_to_collection(
        collection=collection,
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    batch_end_time = time.time()
    if success:
        logging.debug(f"Batch of {len(ids)} records added successfully in {batch_end_time - batch_start_time:.2f} seconds.")
        return len(ids)
    else:
        logging.error(f"Error occurred while adding batch of {len(ids)} records to the database.")
        return 0

# Define the main function of our script
def main():
    logging.info("Starting embedding generation and database loading script...")
    logging.info(f"Sources to process: {DATA_FOLDERS}")
    logging.info(f"Read/Process Batch Size: {PROCESSING_BATCH_SIZE if PROCESSING_BATCH_SIZE else 'All at once'}")
    script_start_time = time.time()

    # Preload required components (Embedding Model & ChromaDB Client)
    logging.info("Preloading required components (Embedding Model & ChromaDB Client)...")
    get_embedding_model()
    get_chroma_client()
    logging.info("Preloading completed.")

    # Variables for total counts
    total_processed_records = 0
    total_added_to_db = 0

    # Loop over our data sources
    for source_name in DATA_FOLDERS:
        logging.info(f"=== Processing source: '{source_name}' ===")
        source_start_time = time.time()
        processed_file = PROCESSED_DATA_DIR / source_name / f"{source_name}_processed.jsonl"  # Path to the processed data file

        # Skip the source if the processed data file doesn't exist
        if not processed_file.is_file():
            logging.warning(f"Processed data file not found, skipping source '{source_name}': {processed_file}")
            print("-" * 50)
            continue

        # Get or create the relevant ChromaDB collection
        collection = get_or_create_collection(source_name)
        if not collection:
            logging.error(f"Could not get or create ChromaDB collection for '{source_name}'. Skipping this source.")
            print("-" * 50)
            continue

        # Initialize counters for this source
        source_processed_count = 0
        source_added_count = 0

        # Read and process data in batches
        data_generator = read_processed_data_batch(processed_file, PROCESSING_BATCH_SIZE)

        # Loop over each batch
        for batch_ids, batch_documents, batch_metadatas in data_generator:
            # If there was an error reading or no data was read
            if not batch_ids:
                logging.warning(f"Data could not be read from source '{source_name}' or it is empty.")
                break  # Stop processing this source

            # Process batches and add to the database
            source_processed_count += len(batch_ids)
            added_count = process_and_add_batch(collection, batch_ids, batch_documents, batch_metadatas)
            source_added_count += added_count
            logging.info(f"Source '{source_name}': {source_processed_count} records read, {source_added_count} added to the database...")

        source_end_time = time.time()
        # Add source counts to totals
        total_processed_records += source_processed_count
        total_added_to_db += source_added_count

        logging.info(f"Source '{source_name}' completed.")
        logging.info(f"  Number of records read: {source_processed_count}")
        logging.info(f"  Number of records added to the database: {source_added_count}")
        logging.info(f"  Elapsed time: {source_end_time - source_start_time:.2f} seconds.")
        logging.info(f"  Updated record count in '{source_name}' collection: {collection.count()}")
        print("-" * 50)

    script_end_time = time.time()
    logging.info("=== All sources processing completed ===")
    logging.info(f"Total number of records read: {total_processed_records}")
    logging.info(f"Total number of records added to the database: {total_added_to_db}")
    logging.info(f"Total elapsed time: {script_end_time - script_start_time:.2f} seconds.")

if __name__ == "__main__":
    # Before running the script, make sure news_fetcher.py and resmi_news_fetcher.py have been called to retrieve the data and
    # that the process_data.py script has been executed to process the retrieved data
    main()
