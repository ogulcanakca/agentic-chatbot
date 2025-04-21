# app/utils/text_processing.py

from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# We define our text cleaning function that uses RecursiveCharacterTextSplitter
def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:

    # If the text is empty or None, we return an empty list
    if not text:
        return []
    try:
        # We try to split the text into paragraphs, then sentences, then words
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", ". ", ", ", " ", ""], 
        )
        chunks = text_splitter.split_text(text)
        # We filter out chunks that consist only of spaces or are too short
        chunks = [chunk for chunk in chunks if chunk.strip()]
        return chunks
    except Exception as e:
        logging.error(f"Error occurred while splitting text: {e}", exc_info=True)
        return []