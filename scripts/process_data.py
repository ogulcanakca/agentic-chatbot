# scripts/process_data.py

import sys
import json
import logging
from pathlib import Path
import hashlib

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.utils.text_processing import split_text
from configs.script_config import DATA_SOURCES, CHUNK_SIZE, CHUNK_OVERLAP, RAW_DATA_DIR, PROCESSED_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Using the SHA-1 hash function from the hashlib module to generate unique IDs
def generate_unique_id(item_data: dict, file_stem: str, item_index: int) -> str:
    # Get title and date information from item_data
    title = item_data.get("title", "")
    date = item_data.get("date", "")
    
    # Combine title and date, pass to hash function
    hasher = hashlib.sha1((title + date).encode('utf-8'))
    content_hash = hasher.hexdigest()[:8]  # Take the first 8 characters
    # Return as a unique ID
    return f"{file_stem}_{item_index}_{content_hash}"

# Function to take raw data stored as JSON files, clean text, and split into chunks
def process_json_list_file(file_path: Path) -> list[dict]:
    logging.info(f"Processing JSON list file: {file_path.name}")
    processed_chunks = []
    file_stem = file_path.stem  # Take the file stem for ID generation

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                # Read the entire file as a JSON list
                data_list = json.load(f)
            except json.JSONDecodeError:
                logging.error(f"JSON file could not be read or is not a list: {file_path.name}")
                return []

        if not isinstance(data_list, list):
            logging.error(f"JSON file does not contain a list: {file_path.name}")
            return []

        if not data_list:
            logging.warning(f"JSON file contains an empty list: {file_path.name}")
            return []

        logging.info(f"-> Found {len(data_list)} items in the file. Processing...")

        # Loop through each item in the list to extract metadata and text
        for item_index, item_data in enumerate(data_list):
            if not isinstance(item_data, dict):
                logging.warning(f"Item {item_index} is not a dict, skipping: {item_data}")
                continue
            
            # Get text content
            text_content = item_data.get('text')
            if not text_content or not isinstance(text_content, str):
                logging.warning(f"Item {item_index}: Invalid or missing 'text' field, skipping.")
                continue

            # Get metadata
            metadata = {k: v for k, v in item_data.items() if k != 'text'}
            # Also add the original source file name
            metadata["original_source_file"] = file_path.name

            # Strip leading and trailing whitespace
            text_content = text_content.strip()
            # If text content is empty after cleaning, skip
            if not text_content:
                logging.warning(f"Item {item_index}: Text content is empty after cleaning, skipping.")
                continue

            # Split text into chunks
            chunks = split_text(text_content, CHUNK_SIZE, CHUNK_OVERLAP)

            # Generate an ID for each chunk and add to the list
            for chunk_index, chunk_text in enumerate(chunks):
                # Generate unique ID for each chunk
                chunk_id = f"{generate_unique_id(item_data, file_stem, item_index)}_{chunk_index}"
                processed_chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": metadata.copy()
                })

        logging.info(f"-> File processed, a total of {len(processed_chunks)} chunks were created.")
        return processed_chunks

    except IOError as e:
        logging.error(f"Error reading file: {file_path}. Error: {e}", exc_info=True)
        return []
    except Exception as e:
        logging.error(f"Unexpected error processing file: {file_path}. Error: {e}", exc_info=True)
        return []

# Define the main function of our script
def main():
    logging.info("Starting data processing (JSON list format)...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)  # Create target main directory if it doesn't exist

    # Define variables to track total processed files and chunk count
    total_files_processed = 0
    total_chunks_generated = 0

    # Start loop over defined data sources
    for source_name, input_filename in DATA_SOURCES.items():
        logging.info(f"=== Processing source: '{source_name}' ===")
        # Path to the raw source file
        source_file_path = RAW_DATA_DIR / source_name / input_filename
        # Path to the directory where processed source file will be saved
        processed_source_dir = PROCESSED_DATA_DIR / source_name
        processed_source_dir.mkdir(parents=True, exist_ok=True)

        # Path to the processed output file
        output_jsonl_path = processed_source_dir / f"{source_name}_processed.jsonl"

        if not source_file_path.is_file():
            logging.warning(f"Source file not found, skipping: {source_file_path}")
            print("-" * 50)
            continue

        # Process the JSON list file and split into chunks
        file_chunks = process_json_list_file(source_file_path)

        # If chunks were generated, update totals and write to file
        if file_chunks:
            total_files_processed += 1
            total_chunks_generated += len(file_chunks)

            # Write processed data to JSON Lines file
            try:
                with open(output_jsonl_path, 'w', encoding='utf-8') as f:
                    for chunk_data in file_chunks:
                        json.dump(chunk_data, f, ensure_ascii=False)
                        f.write('\n')
                logging.info(f"Processed data saved: {output_jsonl_path} ({len(file_chunks)} chunks)")
            except IOError as e:
                logging.error(f"Processed data could not be written: {output_jsonl_path}. Error: {e}")
        else:
            logging.warning(f"No chunks could be generated from file: {source_file_path}")

        print("-" * 50)

    logging.info("=== Data processing completed ===")
    logging.info(f"Total number of processed files: {total_files_processed}")
    logging.info(f"Total number of chunks generated: {total_chunks_generated}")

if __name__ == "__main__":
    # Before running the script, ensure news_fetcher.py and resmi_news_fetcher.py have been executed to retrieve the data
    main()
