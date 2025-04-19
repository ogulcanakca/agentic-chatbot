# app/utils/text_processing.py

from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# RecursiveCharacterTextSplitter'u kullanan metin temizleme fonksiyonumuzu tanımlıyoruz
def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:

    # Metin boşsa veya None ise boş bir liste döndürüyoruz
    if not text:
        return []
    try:
        # Metni paragraflara, sonra cümlelere, sonra kelimelere göre bölmeye çalışıyoruz
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", ". ", ", ", " ", ""], 
        )
        chunks = text_splitter.split_text(text)
        # Sadece boşluklardan oluşan veya çok kısa chunkları filtreleyiyoruz
        chunks = [chunk for chunk in chunks if chunk.strip()]
        return chunks
    except Exception as e:
        logging.error(f"Metin bölünürken hata oluştu: {e}", exc_info=True)
        return []